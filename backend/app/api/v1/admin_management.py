"""阶段 10.2：管理员内容管理增强（只读列表 + 启停用户 + 平台统计）。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies.auth import AdminUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import MUTABLE_GET_CACHE_CONTROL, set_mutation_cache_control
from app.models.enums import UserRole, VideoStatus
from app.schemas.admin_management import (
    AdminBulkDeleteUsersOut,
    AdminPlatformSettingsOut,
    AdminPlatformSettingsUpdate,
    AdminPlatformStatsOut,
    AdminUserActiveBody,
)
from app.schemas.invite_codes import AdminInviteCodeCreate, AdminInviteCodeCreated, AdminInviteCodeItem, AdminInviteCodeListOut
from app.schemas.user import UserPublic
from app.schemas.video import VideoListItem
from app.services import admin_management_service, app_settings_service, invite_code_admin_service

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
    "/invite-codes",
    response_model=AdminInviteCodeListOut,
    summary="邀请码列表",
    description="分页列出内测邀请码及使用状态。",
)
def admin_list_invite_codes(
    db: DbSession,
    _admin: AdminUser,
    offset: _AdminListOffset = 0,
    limit: _AdminListLimit = 50,
) -> AdminInviteCodeListOut:
    return invite_code_admin_service.list_invite_codes(db, offset=offset, limit=limit)


@router.post(
    "/invite-codes",
    response_model=AdminInviteCodeCreated,
    summary="生成邀请码",
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_create_invite_code(
    db: DbSession,
    admin: AdminUser,
    body: AdminInviteCodeCreate,
) -> AdminInviteCodeCreated:
    return invite_code_admin_service.create_invite_code(db, admin, body)


@router.post(
    "/invite-codes/{invite_id}/revoke",
    response_model=AdminInviteCodeItem,
    summary="作废邀请码",
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_revoke_invite_code(db: DbSession, _admin: AdminUser, invite_id: uuid.UUID) -> AdminInviteCodeItem:
    return invite_code_admin_service.revoke_invite_code(db, invite_id)


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


@router.delete(
    "/users/inactive",
    response_model=AdminBulkDeleteUsersOut,
    summary="删除所有未启用用户",
    description="须管理员。软删除全部 ``is_active=false`` 且未删除的用户；已启用用户不受影响。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_delete_inactive_users(db: DbSession, admin: AdminUser) -> AdminBulkDeleteUsersOut:
    return admin_management_service.delete_inactive_users_for_admin(db, admin)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除用户",
    description=(
        "须管理员。软删除用户并禁用账号；被删除用户会从用户列表、登录和用户查询中消失。"
        "不能删除自己，也不能删除最后一个活跃管理员。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
def admin_delete_user(db: DbSession, admin: AdminUser, user_id: uuid.UUID) -> Response:
    admin_management_service.delete_user_for_admin(db, admin, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
