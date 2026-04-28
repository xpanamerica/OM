"""视频下评论：POST/GET 挂在 ``/videos``；DELETE 挂在 ``/comments``。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.dependencies.auth import CurrentUser, OptionalUser
from app.api.deps import DbSession
from app.api.v1.comment_http import weak_etag_for_comment_list_page
from app.api.v1.comment_openapi import (
    COMMENT_DELETE_RESPONSES,
    COMMENT_LIST_GET_RESPONSES,
    COMMENT_POST_RESPONSES,
)
from app.api.v1.http_cache_control import COMMENT_LIST_CACHE_CONTROL, MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.api.v1.video_http import if_none_match_matches
from app.core.comment_cursor import decode_comment_list_cursor, encode_comment_list_cursor
from app.repositories import comment_repository
from app.schemas.comment import CommentCreate, CommentOut
from app.services import comment_service

router = APIRouter()

comments_root_router = APIRouter()


@router.post(
    "/{video_id}/comments",
    response_model=CommentOut,
    summary="发表评论",
    description="须登录；仅 ``published`` 视频可发。一级评论，无回复。",
    responses=COMMENT_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def post_video_comment(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    body: CommentCreate,
):
    c = comment_service.create_comment(db, current_user, video_id, body.content)
    return CommentOut.model_validate(c)


@router.get(
    "/{video_id}/comments",
    response_model=list[CommentOut],
    summary="评论列表",
    description=(
        "未软删除、按创建时间升序。视频可见性与 ``GET /videos/{video_id}`` 一致："
        "已发布可对匿名；非发布仅作者/管理员。"
        "``X-Total-Count`` 为未软删总数。"
        "分页可用 ``limit``/``offset``，或使用 ``cursor``（与 ``offset`` 互斥）；"
        "``cursor`` 为上一页末条评论 id 的 opaque 编码；有下一页时响应头 ``X-Next-Cursor`` 给出。"
        "支持 ``ETag`` / ``If-None-Match``：未变化时 304（无正文）；``Vary: Authorization``。"
    ),
    responses=COMMENT_LIST_GET_RESPONSES,
)
def list_video_comments(
    request: Request,
    response: Response,
    db: DbSession,
    video_id: uuid.UUID,
    viewer: OptionalUser,
    limit: Annotated[int, Query(ge=1, le=200, description="每页条数")] = 50,
    offset: Annotated[int, Query(ge=0, le=500_000, description="偏移")] = 0,
    cursor: Annotated[str | None, Query(description="上一页响应头 ``X-Next-Cursor``（末条评论 id）；与 offset 互斥")] = None,
):
    if cursor and offset:
        raise HTTPException(
            status_code=400,
            detail="cursor 与 offset 不能同时使用，请只传其一。",
        )
    after_comment_id: uuid.UUID | None = None
    if cursor:
        cid = decode_comment_list_cursor(cursor)
        if cid is None:
            raise HTTPException(status_code=400, detail="cursor 无效或已损坏")
        anchor = comment_repository.get_by_id(db, cid)
        if (
            anchor is None
            or anchor.is_deleted
            or anchor.video_id != video_id
        ):
            raise HTTPException(status_code=400, detail="cursor 已失效或不属于该视频")
        after_comment_id = cid
    inm = request.headers.get("if-none-match")
    if inm:
        total_peek, max_u = comment_service.peek_comment_list_aggregate(db, viewer, video_id)
        ck = str(after_comment_id) if after_comment_id else ""
        etag = weak_etag_for_comment_list_page(
            video_id=video_id,
            total=total_peek,
            max_updated_at=max_u,
            limit=limit,
            offset=offset,
            cursor_key=ck,
        )
        if if_none_match_matches(inm, etag):
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": COMMENT_LIST_CACHE_CONTROL,
                    "Vary": "Authorization",
                    "X-Total-Count": str(total_peek),
                },
            )
    rows, total, has_more = comment_service.list_comments(
        db,
        viewer,
        video_id,
        limit=limit,
        offset=offset,
        after_comment_id=after_comment_id,
    )
    max_u = comment_repository.max_updated_at_active_for_video(db, video_id=video_id)
    ck = str(after_comment_id) if after_comment_id else ""
    etag = weak_etag_for_comment_list_page(
        video_id=video_id,
        total=total,
        max_updated_at=max_u,
        limit=limit,
        offset=offset,
        cursor_key=ck,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = COMMENT_LIST_CACHE_CONTROL
    response.headers["ETag"] = etag
    response.headers["Vary"] = "Authorization"
    if has_more and rows:
        last = rows[-1]
        response.headers["X-Next-Cursor"] = encode_comment_list_cursor(comment_id=last.id)
    return [CommentOut.model_validate(x) for x in rows]


@comments_root_router.delete(
    "/{comment_id}",
    status_code=204,
    summary="删除评论（软删除）",
    description="评论作者或管理员；删除后不返回体。",
    responses=COMMENT_DELETE_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def delete_comment(
    db: DbSession,
    comment_id: uuid.UUID,
    current_user: CurrentUser,
) -> Response:
    comment_service.delete_comment(db, current_user, comment_id)
    return Response(status_code=204)
