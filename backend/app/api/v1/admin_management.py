"""阶段 10.2：管理员内容管理增强（只读列表 + 启停用户 + 平台统计）。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies.auth import AdminUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.models.enums import UserRole, VideoStatus
from app.schemas.admin_management import (
    AdminPlatformSettingsOut,
    AdminPlatformSettingsUpdate,
    AdminPlatformStatsOut,
    AdminUserActiveBody,
)
from app.schemas.user import UserPublic
from app.schemas.video import VideoListItem
from app.services import admin_management_service, app_settings_service

router = APIRouter()

_AdminListLimit = Annotated[int, Query(ge=1, le=200, description="分页条数")]
_AdminListOffset = Annotated[int, Query(ge=0, le=1_000_000, description="偏移")]


@router.get("/settings", response_model=AdminPlatformSettingsOut, summary="读取平台设置")
def admin_get_platform_settings(
    response: Response,
    db: DbSession,
    _admin: AdminUser,
) -> AdminPlatformSettingsOut:
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return app_settings_service.get_admin_platform_settings(db)


@router.patch(
    "/settings",
    response_model=AdminPlatformSettingsOut,
    summary="更新平台设置",
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_update_platform_settings(
    db: DbSession,
    _admin: AdminUser,
    body: AdminPlatformSettingsUpdate,
) -> AdminPlatformSettingsOut:
    return app_settings_service.update_admin_platform_settings(db, body)


@router.get(
    "/videos",
    response_model=list[VideoListItem],
    summary="管理员视频列表",
    description=(
        "须管理员；可查看全部状态。支持 ``status`` / ``author_id`` / ``category_id`` / ``keyword``（标题模糊）筛选；"
        "偏移分页。响应头 ``X-Total-Count``。"
    ),
)
def admin_list_videos(
    response: Response,
    db: DbSession,
    _admin: AdminUser,
    offset: _AdminListOffset = 0,
    limit: _AdminListLimit = 50,
    status: VideoStatus | None = Query(default=None, description="按状态筛选"),
    author_id: uuid.UUID | None = Query(default=None, description="作者用户 id"),
    category_id: uuid.UUID | None = Query(default=None, description="分类 id"),
    keyword: str | None = Query(default=None, description="标题关键字（模糊，忽略 %/_ 通配）"),
) -> list[VideoListItem]:
    items, total = admin_management_service.list_admin_videos(
        db,
        offset=offset,
        limit=limit,
        status=status,
        author_id=author_id,
        category_id=category_id,
        keyword=keyword,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return items


@router.get(
    "/users",
    response_model=list[UserPublic],
    summary="管理员用户列表",
    description="须管理员；支持 ``role`` / ``is_active`` / ``keyword``（邮箱或用户名模糊）；偏移分页。",
)
def admin_list_users(
    response: Response,
    db: DbSession,
    _admin: AdminUser,
    offset: _AdminListOffset = 0,
    limit: _AdminListLimit = 50,
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None, description="``true`` / ``false`` 筛选"),
    keyword: str | None = Query(default=None, description="邮箱或用户名关键字"),
) -> list[UserPublic]:
    items, total = admin_management_service.list_admin_users(
        db, offset=offset, limit=limit, role=role, is_active=is_active, keyword=keyword
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return items


@router.patch(
    "/users/{user_id}/active",
    response_model=UserPublic,
    summary="启用或禁用用户",
    description=(
        "须管理员。禁用后 **登录** 将返回 **401**（与口令错误同文案，避免枚举账号状态）。\n\n"
        "**已颁发访问令牌**：JWT 本身在过期前仍可解码；但任意需 ``Authorization`` 的接口在加载用户时"
        "会校验 ``is_active``，停用后立即返回 403「账号已停用」。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_set_user_active(
    db: DbSession,
    admin: AdminUser,
    user_id: uuid.UUID,
    body: AdminUserActiveBody,
) -> UserPublic:
    return admin_management_service.set_user_active_for_admin(
        db, admin, user_id, is_active=body.is_active
    )


@router.get(
    "/statistics/platform",
    response_model=AdminPlatformStatsOut,
    summary="平台基础统计",
    description="须管理员；用户/视频计数与 ``videos`` 表聚合播放量、点赞、收藏总和。",
)
def admin_platform_statistics(
    response: Response,
    db: DbSession,
    _admin: AdminUser,
) -> AdminPlatformStatsOut:
    out = admin_management_service.get_platform_statistics(db)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    return out
