"""播放记录（阶段 9.3）：``POST /videos/{id}/view-record``、``GET /users/me/view-records``。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies.auth import CurrentUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.view_record import ViewRecordOut, ViewRecordUpsertIn
from app.services import view_record_service

videos_router = APIRouter()
users_router = APIRouter()


@videos_router.post(
    "/{video_id}/view-record",
    response_model=ViewRecordOut,
    summary="上报播放记录",
    description="须登录；仅 ``published`` 视频；同一用户对同一视频一行，再次上报更新进度与时间。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def post_video_view_record(
    db: DbSession,
    video_id: uuid.UUID,
    current_user: CurrentUser,
    body: ViewRecordUpsertIn,
) -> ViewRecordOut:
    return view_record_service.upsert_view_record(db, current_user, video_id, body)


@users_router.get(
    "/me/view-records",
    response_model=list[ViewRecordOut],
    summary="我的播放记录",
    description="须登录；按 ``last_viewed_at`` 降序；支持 ``offset`` 或 ``cursor`` 续页；无推荐/复杂筛选。",
)
def get_my_view_records(
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0, description="偏移；与 cursor 互斥")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="条数上限 100")] = 50,
    cursor: Annotated[str | None, Query(description="键集续页（``last_viewed_at``+``id``）；传时须 offset=0")] = None,
) -> list[ViewRecordOut]:
    items, total, next_c, has_more = view_record_service.list_my_view_records(
        db, current_user, offset=offset, limit=limit, cursor_token=cursor
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Has-More"] = "true" if has_more else "false"
    if next_c:
        response.headers["X-Next-Cursor"] = next_c
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return items
