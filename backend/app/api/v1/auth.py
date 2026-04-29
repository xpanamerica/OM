from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.core.client_ip import resolved_client_ip
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.login_rate_limit import is_login_allowed
from app.core.register_rate_limit import is_register_allowed
from app.core.security_audit import (
    log_login_denied,
    log_login_rate_limited,
    log_register_conflict,
    log_register_rate_limited,
)
from app.schemas.auth import Token, UserRegister
from app.schemas.invite_codes import RegistrationOptionsOut
from app.schemas.user import UserPublic
from app.services import app_settings_service, auth_service

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
    if not is_register_allowed(
        ip, max_attempts_per_minute=settings.AUTH_REGISTER_MAX_ATTEMPTS_PER_MINUTE
    ):
        log_register_rate_limited(ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="注册请求过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
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
    if not is_login_allowed(
        ip, max_attempts_per_minute=settings.AUTH_LOGIN_MAX_ATTEMPTS_PER_MINUTE
    ):
        log_login_rate_limited(ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录请求过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
    try:
        user = auth_service.authenticate_user(
            db, login_identifier=form_data.username, password=form_data.password
        )
    except AppError as e:
        if e.status_code == 401:
            log_login_denied(ip)
        raise
    access_token = auth_service.issue_token_for_user(user)
    return Token(access_token=access_token)
