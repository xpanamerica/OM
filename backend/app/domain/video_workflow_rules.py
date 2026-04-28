"""视频审核 / 平台下架：状态边与 PATCH 约束（单一真源）。

合法主路径（阶段 8.2）::

    draft --submit--> pending_review --approve--> published --offline(admin POST)--> offline
                              \\--reject--> rejected
    rejected --(管理员 PATCH)--> draft   # 打回再改
    published --(作者 PATCH offline)--> offline

禁止经 PATCH 走审核边；管理员对已发布下架须 POST /offline。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.exceptions import AppError
from app.core.video_codes import (
    VIDEO_APPROVE_INVALID_STATE,
    VIDEO_OFFLINE_INVALID_STATE,
    VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT,
    VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT,
    VIDEO_REJECT_INVALID_STATE,
    VIDEO_STATUS_TRANSITION_INVALID,
    VIDEO_SUBMIT_INVALID_STATE,
)
from app.models.enums import UserRole, VideoStatus


class WorkflowPostKind(StrEnum):
    """与 `video_workflow_events.action` 及 OpenAPI 路由语义对齐。"""

    SUBMIT_REVIEW = "submit_review"
    APPROVE = "approve"
    REJECT = "reject"
    OFFLINE_ADMIN = "offline_admin"


@dataclass(frozen=True)
class _PostEdge:
    required_from: VideoStatus
    target: VideoStatus
    invalid_message: str
    invalid_code: str


_WORKFLOW_POST_EDGES: dict[WorkflowPostKind, _PostEdge] = {
    WorkflowPostKind.SUBMIT_REVIEW: _PostEdge(
        required_from=VideoStatus.DRAFT,
        target=VideoStatus.PENDING_REVIEW,
        invalid_message="仅草稿状态可提交审核",
        invalid_code=VIDEO_SUBMIT_INVALID_STATE,
    ),
    WorkflowPostKind.APPROVE: _PostEdge(
        required_from=VideoStatus.PENDING_REVIEW,
        target=VideoStatus.PUBLISHED,
        invalid_message="仅待审核状态可通过审核",
        invalid_code=VIDEO_APPROVE_INVALID_STATE,
    ),
    WorkflowPostKind.REJECT: _PostEdge(
        required_from=VideoStatus.PENDING_REVIEW,
        target=VideoStatus.REJECTED,
        invalid_message="仅待审核状态可驳回",
        invalid_code=VIDEO_REJECT_INVALID_STATE,
    ),
    WorkflowPostKind.OFFLINE_ADMIN: _PostEdge(
        required_from=VideoStatus.PUBLISHED,
        target=VideoStatus.OFFLINE,
        invalid_message="仅已发布视频可由管理员下架",
        invalid_code=VIDEO_OFFLINE_INVALID_STATE,
    ),
}

# 与审核专用 POST 重叠的 (old, new)：PATCH 一律拒绝，防绕过
_PATCH_FORBIDDEN_DEDICATED_EDGES: frozenset[tuple[VideoStatus, VideoStatus]] = frozenset(
    {
        (VideoStatus.DRAFT, VideoStatus.PENDING_REVIEW),
        (VideoStatus.PENDING_REVIEW, VideoStatus.PUBLISHED),
        (VideoStatus.PENDING_REVIEW, VideoStatus.REJECTED),
    }
)


def assert_workflow_post_source_status(kind: WorkflowPostKind, current: VideoStatus) -> None:
    """当前状态必须等于该 POST 允许的源状态，否则 400 + 对应 code。"""
    edge = _WORKFLOW_POST_EDGES[kind]
    if current != edge.required_from:
        raise AppError(edge.invalid_message, status_code=400, code=edge.invalid_code)


def workflow_post_target(kind: WorkflowPostKind) -> VideoStatus:
    return _WORKFLOW_POST_EDGES[kind].target


def workflow_event_action(kind: WorkflowPostKind) -> str:
    """写入审计表的 `action` 字段（与 WorkflowPostKind 值一致）。"""
    return kind.value


def assert_patch_status_change_allowed(old: VideoStatus, new: VideoStatus, actor_role: UserRole) -> None:
    """PATCH 修改 `status` 时的业务约束（与历史行为保持一致）。"""
    if new == old:
        return
    if (old, new) in _PATCH_FORBIDDEN_DEDICATED_EDGES:
        raise AppError(
            "该状态变更请使用审核专用接口（提交审核 / 通过 / 驳回）",
            status_code=400,
            code=VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT,
        )
    if old == VideoStatus.PUBLISHED and new == VideoStatus.OFFLINE and actor_role == UserRole.ADMIN:
        raise AppError(
            "管理员对「已发布」视频的平台下架请使用 POST /videos/{id}/offline（勿用 PATCH；作者自行下架仍用 PATCH）",
            status_code=400,
            code=VIDEO_PATCH_ADMIN_OFFLINE_USE_ENDPOINT,
        )
    if actor_role == UserRole.ADMIN and (old, new) == (VideoStatus.REJECTED, VideoStatus.DRAFT):
        return
    if actor_role == UserRole.ADMIN:
        raise AppError(
            "管理员修改视频状态请使用审核/下架专用接口",
            status_code=400,
            code=VIDEO_PATCH_STATUS_USE_DEDICATED_ENDPOINT,
        )
    if old == VideoStatus.PUBLISHED and new == VideoStatus.OFFLINE:
        return
    raise AppError(
        "作者仅可通过 PATCH 将已发布视频改为 offline；其它状态请使用审核流程",
        status_code=400,
        code=VIDEO_STATUS_TRANSITION_INVALID,
    )
