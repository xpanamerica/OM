"""阶段 14：概念节点（管理员维护；公开列表）。"""

from __future__ import annotations

import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DbSession
from app.api.dependencies.auth import OptionalUser, require_admin
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.schemas.concept import ConceptCreate, ConceptLinkedVideoOut, ConceptPublic, ConceptUpdate
from app.services import concept_service

_admin_write = [Depends(require_admin), Depends(set_mutation_cache_control)]

router = APIRouter()


@router.get(
    "",
    response_model=list[ConceptPublic],
    summary="列出概念",
    description="公开；按名称、id 升序。``X-Total-Count`` 为总数。",
)
def list_concepts(
    response: Response,
    db: DbSession,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    rows, total = concept_service.list_concepts(db, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return [ConceptPublic.model_validate(x) for x in rows]


@router.get(
    "/{concept_id}/videos",
    response_model=list[ConceptLinkedVideoOut],
    summary="概念关联的已发布视频",
    description=(
        "公开；仅返回 **已绑定** 且状态为 ``published`` 的视频。"
        "正文为 ``ConceptLinkedVideoOut``：在 ``VideoListItem`` 基础上含 ``start_time_seconds`` / ``end_time_seconds``（管理员标注的片段时间）。"
        "偏移分页，响应头 ``X-Total-Count``；``Vary: Authorization``（与列表脱敏一致）。"
    ),
)
def list_concept_videos(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    concept_id: uuid.UUID,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ConceptLinkedVideoOut]:
    items, total = concept_service.list_published_videos_for_concept(
        db, optional_user, concept_id, offset=offset, limit=limit
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return items


@router.get(
    "/{concept_id}",
    response_model=ConceptPublic,
    summary="概念详情",
    description="公开只读；按主键返回名称与描述等。",
)
def get_concept(db: DbSession, concept_id: uuid.UUID) -> ConceptPublic:
    row = concept_service.get_concept_public(db, concept_id)
    return ConceptPublic.model_validate(row)


@router.post(
    "",
    response_model=ConceptPublic,
    status_code=status.HTTP_201_CREATED,
    summary="创建概念",
    description="需管理员。名称全局唯一（大小写不敏感）。",
    dependencies=_admin_write,
)
def create_concept(db: DbSession, body: ConceptCreate) -> ConceptPublic:
    row = concept_service.create_concept(db, body)
    return ConceptPublic.model_validate(row)


@router.patch(
    "/{concept_id}",
    response_model=ConceptPublic,
    summary="更新概念",
    description="需管理员；可部分更新。",
    dependencies=_admin_write,
)
def update_concept(db: DbSession, concept_id: uuid.UUID, body: ConceptUpdate) -> ConceptPublic:
    row = concept_service.update_concept(db, concept_id, body)
    return ConceptPublic.model_validate(row)
