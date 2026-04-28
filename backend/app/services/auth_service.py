from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import (
    BCRYPT_TIMING_DUMMY_HASH,
    BEARER_WWW_AUTHENTICATE,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.repositories import user_repository
from app.schemas.auth import UserRegister


def register_user(db: Session, payload: UserRegister) -> User:
    email = str(payload.email).strip().lower()
    if user_repository.get_by_email(db, email):
        raise AppError("该邮箱已被注册", status_code=409)
    if user_repository.get_by_username(db, payload.username):
        raise AppError("该用户名已被占用", status_code=409)
    try:
        user = user_repository.create_user(
            db,
            email=email,
            username=payload.username.strip(),
            hashed_password=get_password_hash(payload.password),
        )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise AppError("该邮箱或用户名已被占用", status_code=409)
    return user


def authenticate_user(db: Session, *, login_identifier: str, password: str) -> User:
    login_identifier = login_identifier.strip()
    user = user_repository.get_by_login_identifier(db, login_identifier)
    if user is None:
        verify_password(password, BCRYPT_TIMING_DUMMY_HASH)
        raise AppError("用户名或密码错误", status_code=401, headers=BEARER_WWW_AUTHENTICATE)
    if not verify_password(password, user.hashed_password):
        raise AppError("用户名或密码错误", status_code=401, headers=BEARER_WWW_AUTHENTICATE)
    if not user.is_active:
        # 与口令错误同码同文案，避免枚举「账号存在但已停用」
        raise AppError("用户名或密码错误", status_code=401, headers=BEARER_WWW_AUTHENTICATE)
    return user


def issue_token_for_user(user: User) -> str:
    return create_access_token(subject=str(user.id))
