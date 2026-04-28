"""阶段 10.2：管理员内容管理（视频列表、用户列表、启停用户、平台统计）。"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.admin_codes import (
    ADMIN_CANNOT_DELETE_LAST_ACTIVE_ADMIN,
    ADMIN_CANNOT_DELETE_SELF,
    ADMIN_CANNOT_DISABLE_LAST_ACTIVE_ADMIN,
    ADMIN_CANNOT_DISABLE_SELF,
    ADMIN_USER_NOT_FOUND,
)
from app.core.exceptions import AppError
from app.models.enums import UserRole, VideoStatus
from app.models.user import User
from app.repositories import user_repository, video_repository
from app.schemas.admin_management import AdminBulkDeleteUsersOut, AdminPlatformStatsOut
from app.schemas.user import UserPublic
from app.schemas.video import VideoListItem


def list_admin_videos(
    db: Session,
    *,
    offset: int,
    limit: int,
    status: VideoStatus | None,
    author_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    keyword: str | None,
) -> tuple[list[VideoListItem], int]:
    rows = video_repository.list_videos_for_admin(
        db,
        offset=offset,
        limit=limit,
        status=status,
        author_id=author_id,
        category_id=category_id,
        keyword=keyword,
    )
    total = video_repository.count_videos_for_admin(
        db,
        status=status,
        author_id=author_id,
        category_id=category_id,
        keyword=keyword,
    )
    return [VideoListItem.model_validate(v) for v in rows], total


def list_admin_users(
    db: Session,
    *,
    offset: int,
    limit: int,
    role: UserRole | None,
    is_active: bool | None,
    keyword: str | None,
) -> tuple[list[UserPublic], int]:
    rows = user_repository.list_users_for_admin(
        db, offset=offset, limit=limit, role=role, is_active=is_active, keyword=keyword
    )
    total = user_repository.count_users_for_admin(db, role=role, is_active=is_active, keyword=keyword)
    return [UserPublic.model_validate(u) for u in rows], total


def set_user_active_for_admin(db: Session, actor: User, user_id: uuid.UUID, *, is_active: bool) -> UserPublic:
    if not is_active:
        if actor.id == user_id:
            raise AppError("不能禁用自己的账号", status_code=403, code=ADMIN_CANNOT_DISABLE_SELF)
        target = user_repository.get_by_id(db, user_id)
        if target is None:
            raise AppError("用户不存在", status_code=404, code=ADMIN_USER_NOT_FOUND)
        if target.role == UserRole.ADMIN:
            others = user_repository.count_active_admins_excluding(db, exclude_user_id=user_id)
            if others < 1:
                raise AppError(
                    "不能禁用最后一个活跃管理员账号",
                    status_code=400,
                    code=ADMIN_CANNOT_DISABLE_LAST_ACTIVE_ADMIN,
                )
    u = user_repository.set_user_is_active(db, user_id=user_id, is_active=is_active)
    if u is None:
        raise AppError("用户不存在", status_code=404, code=ADMIN_USER_NOT_FOUND)
    db.commit()
    db.refresh(u)
    return UserPublic.model_validate(u)


def delete_user_for_admin(db: Session, actor: User, user_id: uuid.UUID) -> None:
    if actor.id == user_id:
        raise AppError("不能删除自己的账号", status_code=403, code=ADMIN_CANNOT_DELETE_SELF)
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise AppError("用户不存在", status_code=404, code=ADMIN_USER_NOT_FOUND)
    if target.role == UserRole.ADMIN and target.is_active:
        others = user_repository.count_active_admins_excluding(db, exclude_user_id=user_id)
        if others < 1:
            raise AppError(
                "不能删除最后一个活跃管理员账号",
                status_code=400,
                code=ADMIN_CANNOT_DELETE_LAST_ACTIVE_ADMIN,
            )
    deleted = user_repository.soft_delete_user(db, user_id=user_id)
    if deleted is None:
        raise AppError("用户不存在", status_code=404, code=ADMIN_USER_NOT_FOUND)
    db.commit()


def delete_inactive_users_for_admin(db: Session, _actor: User) -> AdminBulkDeleteUsersOut:
    deleted = user_repository.soft_delete_inactive_users(db)
    db.commit()
    return AdminBulkDeleteUsersOut(deleted=deleted)


def get_platform_statistics(db: Session) -> AdminPlatformStatsOut:
    users_total = user_repository.count_alive_users(db)
    videos_total = video_repository.count_videos_total(db)
    published = video_repository.count_videos_by_status(db, status=VideoStatus.PUBLISHED)
    pending = video_repository.count_videos_by_status(db, status=VideoStatus.PENDING_REVIEW)
    tv, tl, tf = video_repository.aggregate_video_counter_totals(db)
    return AdminPlatformStatsOut(
        users_total=users_total,
        videos_total=videos_total,
        videos_published=published,
        videos_pending_review=pending,
        total_views_count=tv,
        total_likes_count=tl,
        total_favorites_count=tf,
    )
