"""认证与当前用户相关依赖（JWT Bearer）。"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.api.deps import DbSession
from app.core.config import settings
from app.core.security import BEARER_WWW_AUTHENTICATE, decode_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import user_mfa_repository, user_repository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证",
            headers=BEARER_WWW_AUTHENTICATE,
        )
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers=BEARER_WWW_AUTHENTICATE,
        )
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers=BEARER_WWW_AUTHENTICATE,
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_user_optional(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User | None:
    """已登录则返回用户；无 Token 则匿名。携带无效/过期 Token 仍返回 401。"""
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers=BEARER_WWW_AUTHENTICATE,
        )
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers=BEARER_WWW_AUTHENTICATE,
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    return user


OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


def require_admin(db: DbSession, user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    mfa = user_mfa_repository.get(db, user_id=user.id)
    if not (mfa and mfa.enabled and mfa.totp_secret_sealed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理员必须先启用 MFA")
    return user


AdminUser = Annotated[User, Depends(require_admin)]

# 兼容旧命名
require_superuser = require_admin
SuperUser = AdminUser
