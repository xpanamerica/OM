from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


def _alive_filter(stmt):
    return stmt.where(User.deleted_at.is_(None))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    stmt = _alive_filter(select(User).where(User.id == user_id))
    return db.execute(stmt).scalar_one_or_none()


def get_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    stmt = _alive_filter(select(User).where(User.email == normalized))
    return db.execute(stmt).scalar_one_or_none()


def get_by_username(db: Session, username: str) -> User | None:
    stmt = _alive_filter(select(User).where(User.username == username.strip()))
    return db.execute(stmt).scalar_one_or_none()


def get_by_login_identifier(db: Session, identifier: str) -> User | None:
    """OAuth2 `username` 字段可填用户名或邮箱；邮箱按小写匹配，用户名大小写不敏感。"""
    ident = identifier.strip()
    if not ident:
        return None
    if "@" in ident:
        stmt = _alive_filter(select(User).where(User.email == ident.lower()))
    else:
        stmt = _alive_filter(select(User).where(func.lower(User.username) == ident.lower()))
    return db.execute(stmt).scalar_one_or_none()


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
    hashed_password: str,
    role: UserRole = UserRole.USER,
) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password=hashed_password,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _admin_user_keyword_clause(keyword: str | None):
    if not keyword or not keyword.strip():
        return None
    k = keyword.strip()[:200].replace("%", "").replace("_", "")
    if not k:
        return None
    pat = f"%{k}%"
    return or_(User.email.ilike(pat), User.username.ilike(pat))


def _apply_admin_user_list_filters(
    stmt,
    *,
    role: UserRole | None,
    is_active: bool | None,
    keyword: str | None,
):
    stmt = _alive_filter(stmt)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    kw = _admin_user_keyword_clause(keyword)
    if kw is not None:
        stmt = stmt.where(kw)
    return stmt


def list_users_for_admin(
    db: Session,
    *,
    offset: int,
    limit: int,
    role: UserRole | None,
    is_active: bool | None,
    keyword: str | None,
) -> list[User]:
    stmt = (
        _apply_admin_user_list_filters(select(User), role=role, is_active=is_active, keyword=keyword)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def count_users_for_admin(
    db: Session,
    *,
    role: UserRole | None,
    is_active: bool | None,
    keyword: str | None,
) -> int:
    stmt = _apply_admin_user_list_filters(
        select(func.count(User.id)).select_from(User),
        role=role,
        is_active=is_active,
        keyword=keyword,
    )
    return int(db.execute(stmt).scalar_one())


def count_alive_users(db: Session) -> int:
    return int(db.scalar(_alive_filter(select(func.count(User.id)).select_from(User))) or 0)


def count_active_admins_excluding(db: Session, *, exclude_user_id: uuid.UUID) -> int:
    stmt = _alive_filter(
        select(func.count(User.id)).select_from(User).where(
            and_(User.role == UserRole.ADMIN, User.is_active == True, User.id != exclude_user_id)  # noqa: E712
        )
    )
    return int(db.scalar(stmt) or 0)


def set_user_is_active(db: Session, *, user_id: uuid.UUID, is_active: bool) -> User | None:
    u = get_by_id(db, user_id)
    if u is None:
        return None
    u.is_active = is_active
    db.add(u)
    db.flush()
    return u
