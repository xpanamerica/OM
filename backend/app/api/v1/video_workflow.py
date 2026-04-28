"""审核与平台下架等专用 POST，与 CRUD 路由拆分以降低 `videos.py` 体积并便于演进。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.api.v1.video_openapi import (
    VIDEO_WORKFLOW_EVENTS_GET_RESPONSES,
    VIDEO_WORKFLOW_POST_RESPONSES,
)
from app.api.dependencies.auth import CurrentUser
from app.api.v1.video_query import WorkflowAuditCursor, WorkflowAuditLimit, WorkflowAuditOffset
from app.schemas.video import VideoRejectRequest, VideoResponse, VideoWorkflowEventOut
from app.services import video_service

router = APIRouter()


@router.get(
    "/{video_id}/workflow-events",
    response_model=list[VideoWorkflowEventOut],
    summary="工作流审计列表",
    description=(
        "按时间正序返回 submit/approve/reject/offline 等审计记录。"
        "**管理员**可查看任意视频；**作者**仅可查看本人视频（便于对账与申诉材料）。"
        "其他身份返回 403。"
        "分页：`offset`+`limit` 或 `cursor`+`limit`（游标为工作流专用：`created_at`+`audit_sequence`，见响应头 `X-Next-Cursor`），二者互斥。"
    ),
    responses=VIDEO_WORKFLOW_EVENTS_GET_RESPONSES,
)
def list_video_workflow_events(
    response: Response,
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    offset: WorkflowAuditOffset = 0,
    limit: WorkflowAuditLimit = 50,
    cursor: WorkflowAuditCursor = None,
):
    items, total, has_more, next_cursor = video_service.list_video_workflow_events(
        db, current_user, video_id, offset=offset, limit=limit, cursor=cursor
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-More"] = "true" if has_more else "false"
    if has_more and next_cursor:
        response.headers["X-Next-Cursor"] = next_cursor
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return [VideoWorkflowEventOut.model_validate(x) for x in items]


@router.post(
    "/{video_id}/submit-review",
    response_model=VideoResponse,
    summary="提交审核",
    description="仅作者或管理员。仅允许 `draft` → `pending_review`。",
    responses=VIDEO_WORKFLOW_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def submit_video_review(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoResponse:
    v = video_service.submit_video_for_review(db, current_user, video_id)
    return VideoResponse.model_validate(v)


@router.post(
    "/{video_id}/approve",
    response_model=VideoResponse,
    summary="审核通过",
    description="仅管理员。仅允许 `pending_review` → `published`；首次发布写入 `published_at`。",
    responses=VIDEO_WORKFLOW_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def approve_video(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoResponse:
    v = video_service.approve_video(db, current_user, video_id)
    return VideoResponse.model_validate(v)


@router.post(
    "/{video_id}/reject",
    response_model=VideoResponse,
    summary="审核驳回",
    description="仅管理员。仅允许 `pending_review` → `rejected`；须提供 `rejection_reason`。",
    responses=VIDEO_WORKFLOW_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def reject_video(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    body: VideoRejectRequest,
) -> VideoResponse:
    v = video_service.reject_video(db, current_user, video_id, body)
    return VideoResponse.model_validate(v)


@router.post(
    "/{video_id}/offline",
    response_model=VideoResponse,
    summary="管理员下架（平台）",
    description=(
        "**平台侧**将已上线视频下线：仅管理员，且仅 `published` → `offline`。"
        "与「作者自行下架」不同：作者对自己已发布内容请使用 **PATCH** 将 `status` 改为 `offline`（见「更新视频」说明），勿与本接口混淆。"
    ),
    responses=VIDEO_WORKFLOW_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def offline_video_admin(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
) -> VideoResponse:
    v = video_service.offline_video_by_admin(db, current_user, video_id)
    return VideoResponse.model_validate(v)
