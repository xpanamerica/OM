"""阶段 14：学习路径（登录用户可创建；创建者或管理员可改）。"""

from __future__ import annotations

import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DbSession
from app.api.dependencies.auth import CurrentUser, OptionalUser
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathDetail,
    LearningPathItemsPut,
    LearningPathPublic,
    LearningPathUpdate,
)
from app.services import learning_path_service

router = APIRouter()


@router.get(
    "",
    response_model=list[LearningPathPublic],
    summary="列出学习路径",
    description=(
        "匿名仅 ``is_published``；登录用户另含本人未发布路径；管理员列出全部。"
        "``X-Total-Count``；``Vary: Authorization``。"
    ),
)
def list_learning_paths(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    rows, total = learning_path_service.list_paths(db, optional_user, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return [LearningPathPublic.model_validate(x) for x in rows]


@router.post(
    "",
    response_model=LearningPathPublic,
    status_code=status.HTTP_201_CREATED,
    summary="创建学习路径",
    description="需登录；创建者为当前用户。可选附带 ``items``。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def create_learning_path(db: DbSession, current_user: CurrentUser, body: LearningPathCreate) -> LearningPathPublic:
    row = learning_path_service.create_path(db, current_user, body)
    return LearningPathPublic.model_validate(row)


@router.get(
    "/{path_id}",
    response_model=LearningPathDetail,
    summary="学习路径详情",
    description="未发布路径仅创建者或管理员可查看。条目内 ``video`` 按单视频可见性脱敏。",
)
def get_learning_path(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    path_id: uuid.UUID,
) -> LearningPathDetail:
    detail = learning_path_service.get_path_detail(db, optional_user, path_id)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return detail


@router.patch(
    "/{path_id}",
    response_model=LearningPathPublic,
    summary="更新学习路径元数据",
    description="创建者或管理员。若 ``is_published`` 为 true，所含视频须均为已发布。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def patch_learning_path(
    db: DbSession,
    current_user: CurrentUser,
    path_id: uuid.UUID,
    body: LearningPathUpdate,
) -> LearningPathPublic:
    row = learning_path_service.update_path(db, current_user, path_id, body)
    return LearningPathPublic.model_validate(row)


@router.put(
    "/{path_id}/items",
    status_code=204,
    summary="替换学习路径条目",
    description="创建者或管理员。已发布路径仅允许引用已发布视频。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def put_learning_path_items(
    db: DbSession,
    current_user: CurrentUser,
    path_id: uuid.UUID,
    body: LearningPathItemsPut,
) -> Response:
    learning_path_service.replace_path_items(db, current_user, path_id, body)
    return Response(status_code=204)
