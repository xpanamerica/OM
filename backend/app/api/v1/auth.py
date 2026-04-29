from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.core import auth_rate_limit
from app.core.client_ip import resolved_client_ip
from app.core.config import settings
from app.core.exceptions import AppError, AuthRateLimitExceeded
from app.core.security_audit import (
    log_login_denied,
    log_login_rate_limited,
    log_register_conflict,
    log_register_rate_limited,
)
from app.repositories import security_event_repository
from app.schemas.auth import (
    ForgotPasswordIn,
    ForgotPasswordOut,
    ResetPasswordIn,
    ResetPasswordOut,
    Token,
    UserRegister,
)
from app.schemas.invite_codes import RegistrationOptionsOut
from app.schemas.user import UserPublic
from app.services import app_settings_service, auth_service, password_reset_service

router = APIRouter()


@router.get(
    "/registration-options",
    response_model=RegistrationOptionsOut,
    summary="公开注册策略（是否强制邀请码）",
)
def registration_options(db: DbSession) -> RegistrationOptionsOut:
    return RegistrationOptionsOut(
        invite_code_required=app_settings_service.is_registration_invite_code_required(db)
    )


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=201,
    dependencies=[Depends(set_mutation_cache_control)],
)
def register(request: Request, db: DbSession, body: UserRegister) -> UserPublic:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    ok, retry_after, which = auth_rate_limit.try_consume_register(ip)
    if not ok:
        log_register_rate_limited(ip)
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.register",
            ip_address=ip,
            subject_hash=None,
            detail=which,
        )
        raise AuthRateLimitExceeded(retry_after=retry_after)
    ua = request.headers.get("user-agent") or request.headers.get("User-Agent")
    try:
        user = auth_service.register_user(db, body, client_ip=ip, user_agent=ua)
    except AppError as e:
        if e.status_code == 409:
            log_register_conflict(ip)
        raise
    return UserPublic.model_validate(user)


@router.post("/login", response_model=Token, dependencies=[Depends(set_mutation_cache_control)])
def login(
    request: Request,
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    ok, retry_after = auth_rate_limit.try_consume_login_ip(ip)
    if not ok:
        log_login_rate_limited(ip)
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.login_ip",
            ip_address=ip,
            subject_hash=None,
            detail="login_per_ip",
        )
        raise AuthRateLimitExceeded(retry_after=retry_after)

    if auth_rate_limit.is_login_account_blocked(form_data.username):
        auth_rate_limit.notify_login_fail_account_rate_limited()
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.login_account",
            ip_address=ip,
            subject_hash=auth_rate_limit.login_account_subject_hash(form_data.username),
            detail="login_failures_per_account",
        )
        raise AuthRateLimitExceeded()

    try:
        user = auth_service.authenticate_user(
            db, login_identifier=form_data.username, password=form_data.password
        )
    except AppError as e:
        if e.status_code == 401:
            log_login_denied(ip)
            auth_rate_limit.record_login_failure(form_data.username)
        raise
    auth_rate_limit.clear_login_failures(form_data.username)
    access_token = auth_service.issue_token_for_user(user)
    return Token(access_token=access_token)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordOut,
    status_code=status.HTTP_200_OK,
    summary="忘记密码",
    description=(
        "防邮箱枚举：无论邮箱是否存在，HTTP 200 与相同 JSON 文案。"
        "对已注册且启用的用户：签发一次性令牌（``password_reset_tokens``），并按 "
        "``AUTH_PASSWORD_RESET_EMAIL_BACKEND``（noop/log/smtp）投递。"
        "启用限流时写 Redis。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
def forgot_password(request: Request, db: DbSession, body: ForgotPasswordIn) -> ForgotPasswordOut:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    email_norm = str(body.email).strip().lower()
    ok, retry_after, which = auth_rate_limit.try_consume_forgot_password(ip, email_norm)
    if not ok:
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.forgot_password",
            ip_address=ip,
            subject_hash=auth_rate_limit.subject_fingerprint(email_norm),
            detail=which,
        )
        raise AuthRateLimitExceeded(retry_after=retry_after)
    password_reset_service.request_password_reset(db, email_normalized=email_norm, client_ip=ip)
    return ForgotPasswordOut()


@router.post(
    "/reset-password",
    response_model=ResetPasswordOut,
    status_code=status.HTTP_200_OK,
    summary="使用邮件令牌重置密码",
    description="消费 ``forgot-password`` 签发的明文令牌，设置新密码；成功后可立即用新口令登录。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def reset_password(request: Request, db: DbSession, body: ResetPasswordIn) -> ResetPasswordOut:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    password_reset_service.complete_password_reset(
        db,
        raw_token=body.token,
        new_password=body.password,
        client_ip=ip,
    )
    return ResetPasswordOut()
