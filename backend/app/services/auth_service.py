from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import (
    BCRYPT_TIMING_DUMMY_HASH,
    BEARER_WWW_AUTHENTICATE,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.invite_code import InviteCode
from app.models.user import User
from app.repositories import invite_code_repository, registration_attempt_repository, user_repository
from app.schemas.auth import UserRegister
from app.services import app_settings_service

_log = logging.getLogger("app.auth")


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _invite_validation_message(invite: InviteCode, *, now: datetime) -> str | None:
    if invite.status == "revoked":
        return "邀请码已作废"
    if invite.status != "active":
        return "邀请码无效或已失效"
    if invite.expires_at is not None and _as_utc(invite.expires_at) <= now:
        return "邀请码已过期"
    if invite.used_count >= invite.max_uses:
        return "邀请码已用完"
    return None


def _redeem_invite(invite: InviteCode, *, user_id: uuid.UUID, now: datetime) -> None:
    invite.used_count += 1
    invite.used_by = user_id
    invite.used_at = now
    if invite.used_count >= invite.max_uses:
        invite.status = "used"


def register_user(
    db: Session,
    payload: UserRegister,
    *,
    client_ip: str,
    user_agent: str | None,
) -> User:
    invite_required = app_settings_service.is_registration_invite_code_required(db)
    submitted = payload.invite_code or ""
    email = str(payload.email).strip().lower()
    username_stripped = payload.username.strip()

    def audit(
        *,
        success: bool,
        failure_reason: str | None = None,
        created_user_id: uuid.UUID | None = None,
    ) -> None:
        registration_attempt_repository.record_registration_attempt(
            ip_address=client_ip,
            user_agent=user_agent,
            email=email,
            username=username_stripped,
            invite_code_submitted=submitted or None,
            success=success,
            failure_reason=failure_reason,
            created_user_id=created_user_id,
        )

    invite_row: InviteCode | None = None
    now = datetime.now(UTC)

    try:
        if invite_required and not submitted:
            audit(success=False, failure_reason="当前为内测阶段，请输入邀请码。")
            raise AppError("当前为内测阶段，请输入邀请码。", status_code=400)

        if user_repository.get_by_email(db, email):
            audit(success=False, failure_reason="该邮箱已被注册")
            raise AppError("该邮箱已被注册", status_code=409)
        if user_repository.get_by_username(db, username_stripped):
            audit(success=False, failure_reason="该用户名已被占用")
            raise AppError("该用户名已被占用", status_code=409)

        if invite_required:
            invite_row = invite_code_repository.get_by_code_for_update(db, submitted)
            if invite_row is None:
                audit(success=False, failure_reason="邀请码无效或已失效")
                raise AppError("邀请码无效或已失效", status_code=400)
            msg = _invite_validation_message(invite_row, now=now)
            if msg:
                audit(success=False, failure_reason=msg)
                raise AppError(msg, status_code=400)

        user = user_repository.create_user(
            db,
            email=email,
            username=username_stripped,
            hashed_password=get_password_hash(payload.password),
            is_active=not settings.AUTH_REGISTRATION_REQUIRES_APPROVAL,
        )
        db.flush()
        if invite_required and invite_row is not None:
            _redeem_invite(invite_row, user_id=user.id, now=now)
        db.commit()
        db.refresh(user)
        try:
            audit(success=True, created_user_id=user.id)
        except Exception:
            _log.exception("registration_success_audit_failed user_id=%s", user.id)
        return user
    except AppError:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        audit(success=False, failure_reason="该邮箱或用户名已被占用")
        raise AppError("该邮箱或用户名已被占用", status_code=409)


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
