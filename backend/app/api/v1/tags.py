from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from starlette.responses import Response

from app.api.deps import DbSession
from app.api.dependencies.auth import require_admin
from app.api.v1.taxonomy_openapi import (
    ADMIN_CREATE_RESPONSES,
    LIST_GET_RESPONSES,
    NAME_CONFLICT,
    NOT_FOUND_TAG,
    UNAUTH_OR_FORBIDDEN,
)
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.api.v1.taxonomy_http import TAXONOMY_LIST_CACHE_CONTROL
from app.api.v1.taxonomy_query import TaxonomyListCursor, TaxonomyListLimit, TaxonomyListOffset
from app.schemas.tag import TagCreate, TagPublic, TagUpdate
from app.services import tag_service
from app.services.taxonomy_list import next_cursor_token

_admin_write = [Depends(require_admin), Depends(set_mutation_cache_control)]

router = APIRouter()


@router.get(
    "",
    response_model=list[TagPublic],
    summary="列出标签",
    description=(
        "公开接口，无需登录。按 (name, id) 升序。"
        "分页：`limit` 省略则全量；此时 `offset`≠0 返回 400。"
        "可选 `cursor` 键集续页（与 `offset` 互斥，且必须带 `limit`）。"
        "带 `limit` 时含 `X-Has-More`；若有下一页则另含 `X-Next-Cursor` 可直接作下一页 `cursor`。"
        "响应含 `Cache-Control`（见 OpenAPI），避免共享缓存陈旧列表。"
    ),
    responses=LIST_GET_RESPONSES,
)
def list_tags(
    response: Response,
    db: DbSession,
    limit: TaxonomyListLimit = None,
    offset: TaxonomyListOffset = 0,
    cursor: TaxonomyListCursor = None,
):
    items, has_more = tag_service.list_tags(db, limit=limit, offset=offset, cursor=cursor)
    response.headers["Cache-Control"] = TAXONOMY_LIST_CACHE_CONTROL
    if limit is not None:
        response.headers["X-Has-More"] = "true" if has_more else "false"
        if has_more and items:
            last = items[-1]
            response.headers["X-Next-Cursor"] = next_cursor_token(name=last.name, row_id=last.id)
    return items


@router.post(
    "",
    response_model=TagPublic,
    status_code=status.HTTP_201_CREATED,
    summary="创建标签",
    description="需管理员 JWT。`name` 经 NFKC 与 trim 后须全局唯一（大小写不敏感）。",
    responses=ADMIN_CREATE_RESPONSES,
    dependencies=_admin_write,
)
def create_tag(db: DbSession, body: TagCreate) -> TagPublic:
    row = tag_service.create_tag(db, body)
    return TagPublic.model_validate(row)


@router.patch(
    "/{tag_id}",
    response_model=TagPublic,
    summary="更新标签",
    description="需管理员 JWT。可部分更新；若修改 `name` 则不得与已有标签重名。",
    responses={**UNAUTH_OR_FORBIDDEN, **NOT_FOUND_TAG, **NAME_CONFLICT},
    dependencies=_admin_write,
)
def update_tag(db: DbSession, tag_id: uuid.UUID, body: TagUpdate) -> TagPublic:
    row = tag_service.update_tag(db, tag_id, body)
    return TagPublic.model_validate(row)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="删除标签",
    description="需管理员 JWT；物理删除记录。",
    responses={**UNAUTH_OR_FORBIDDEN, **NOT_FOUND_TAG},
    dependencies=_admin_write,
)
def delete_tag(
    response: Response,
    db: DbSession,
    tag_id: uuid.UUID,
) -> Response:
    tag_service.delete_tag(db, tag_id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
