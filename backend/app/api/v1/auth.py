from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies.auth import CurrentUser, OptionalUser
from app.api.deps import DbSession
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.core import auth_rate_limit
from app.core.client_ip import resolved_client_ip
from app.core.config import settings
from app.core.csrf import generate_csrf_token, verify_csrf_request
from app.core.exceptions import AppError, AuthRateLimitExceeded
from app.core.security import BEARER_WWW_AUTHENTICATE
from app.core.security_audit import (
    log_login_denied,
    log_login_rate_limited,
    log_register_conflict,
    log_register_rate_limited,
)
from app.repositories import security_event_repository, user_auth_state_repository, user_repository
from app.schemas.auth import (
    AuthSessionsOut,
    ForgotPasswordIn,
    ForgotPasswordOut,
    MfaDisableIn,
    MfaEnableIn,
    MfaEnableOut,
    MfaSetupIn,
    MfaSetupOut,
    MfaStatusOut,
    MfaVerifyLoginIn,
    RevokeOtherSessionsOut,
    ResetPasswordIn,
    ResetPasswordOut,
    Token,
    UserRegister,
)
from app.schemas.invite_codes import RegistrationOptionsOut
from app.schemas.user import UserPublic
from app.services import (
    app_settings_service,
    auth_service,
    mfa_service,
    password_reset_service,
    refresh_token_service,
    turnstile_service,
)

router = APIRouter()


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent") or request.headers.get("User-Agent")


def _request_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request.headers.get("X-Request-ID")


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_token,
        max_age=refresh_token_service.refresh_token_ttl_seconds(),
        expires=refresh_token_service.refresh_token_ttl_seconds(),
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )


def _set_csrf_cookie(response: Response) -> str:
    token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        max_age=refresh_token_service.refresh_token_ttl_seconds(),
        expires=refresh_token_service.refresh_token_ttl_seconds(),
        path="/",
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=False,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )
    return token


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path="/",
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=False,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )


def _issue_login_tokens(
    *,
    db,
    request: Request,
    response: Response,
    user,
    ip: str,
    user_agent: str | None,
) -> Token:
    user_auth_state_repository.clear_failures(db, user_id=user.id)
    access_token = auth_service.issue_token_for_user(user)
    issued_refresh = refresh_token_service.issue_refresh_token(
        db,
        user=user,
        ip_address=ip,
        user_agent=user_agent,
    )
    db.commit()
    _set_refresh_cookie(response, issued_refresh.raw_token)
    _set_csrf_cookie(response)
    security_event_repository.insert_event_sync(
        event_type="auth.login.succeeded",
        user_id=user.id,
        ip_address=ip,
        subject_hash=auth_rate_limit.subject_fingerprint(str(user.id)),
        detail=None,
        request_id=_request_id(request),
        user_agent=user_agent,
        metadata={"mfa": mfa_service.is_mfa_enabled(db, user_id=user.id)},
    )
    return Token(access_token=access_token)


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
    turnstile_service.verify_turnstile_token(body.turnstile_token, remote_ip=ip, expected_action="register")
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
    response: Response,
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    turnstile_token: Annotated[str | None, Form()] = None,
) -> Token:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    ua = _request_user_agent(request)
    rid = _request_id(request)
    ok, retry_after = auth_rate_limit.try_consume_login_ip(ip)
    if not ok:
        log_login_rate_limited(ip)
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.login_ip",
            ip_address=ip,
            subject_hash=None,
            detail="login_per_ip",
            request_id=rid,
            user_agent=ua,
        )
        raise AuthRateLimitExceeded(retry_after=retry_after)

    existing_user = user_repository.get_by_login_identifier(db, form_data.username)
    if existing_user is not None and user_auth_state_repository.locked_until_if_active(
        db, user_id=existing_user.id
    ):
        auth_rate_limit.notify_login_fail_account_rate_limited()
        security_event_repository.insert_event_sync(
            event_type="auth.login.locked",
            user_id=existing_user.id,
            ip_address=ip,
            subject_hash=auth_rate_limit.login_account_subject_hash(form_data.username),
            detail="login_failures_per_account",
            request_id=rid,
            user_agent=ua,
        )
        raise AppError(
            refresh_token_service.AUTH_FAILED_MESSAGE,
            status_code=401,
            headers=BEARER_WWW_AUTHENTICATE,
        )

    if auth_rate_limit.login_account_failure_count(form_data.username) >= settings.TURNSTILE_LOGIN_FAILURE_THRESHOLD:
        turnstile_service.verify_turnstile_token(turnstile_token, remote_ip=ip, expected_action="login")

    try:
        user = auth_service.authenticate_user(
            db, login_identifier=form_data.username, password=form_data.password
        )
    except AppError as e:
        if e.status_code == 401:
            log_login_denied(ip)
            auth_rate_limit.record_login_failure(form_data.username)
            if existing_user is not None:
                user_auth_state_repository.record_failure(db, user_id=existing_user.id)
                db.commit()
            security_event_repository.insert_event_sync(
                event_type="auth.login.failed",
                user_id=existing_user.id if existing_user is not None else None,
                ip_address=ip,
                subject_hash=auth_rate_limit.login_account_subject_hash(form_data.username),
                detail="bad_credentials",
                request_id=rid,
                user_agent=ua,
            )
        raise
    if mfa_service.setup_required_for_user(db, user):
        return Token(
            mfa_required=True,
            mfa_setup_required=True,
            mfa_challenge_token=mfa_service.create_challenge_token(user_id=user.id, setup_required=True),
        )
    if mfa_service.mfa_required_for_user(db, user):
        return Token(
            mfa_required=True,
            mfa_challenge_token=mfa_service.create_challenge_token(user_id=user.id),
        )
    auth_rate_limit.clear_login_failures(form_data.username)
    return _issue_login_tokens(db=db, request=request, response=response, user=user, ip=ip, user_agent=ua)


@router.post("/mfa/verify-login", response_model=Token, dependencies=[Depends(set_mutation_cache_control)])
def verify_mfa_login(request: Request, response: Response, db: DbSession, body: MfaVerifyLoginIn) -> Token:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    challenge = mfa_service.decode_challenge(body.mfa_challenge_token)
    ok, retry_after = auth_rate_limit.try_consume_mfa_attempt(
        challenge_token=body.mfa_challenge_token,
        client_ip=ip,
        user_id=str(challenge.user_id) if challenge else None,
    )
    if not ok:
        security_event_repository.insert_event_sync(
            event_type="rate_limit.auth.mfa",
            ip_address=ip,
            detail="mfa_challenge",
            request_id=_request_id(request),
            user_agent=_request_user_agent(request),
        )
        raise AuthRateLimitExceeded(retry_after=retry_after)
    user = user_repository.get_by_id(db, challenge.user_id) if challenge is not None else None
    if user is None or not user.is_active or not mfa_service.verify_user_mfa(db, user=user, code=body.code):
        if user is not None:
            mfa_service.audit_mfa_event(
                event_type="auth.mfa.login_failed",
                user=user,
                ip_address=ip,
                detail="bad_mfa_code",
            )
        raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401, code=mfa_service.MFA_INVALID_CODE)
    mfa_service.audit_mfa_event(event_type="auth.mfa.login_succeeded", user=user, ip_address=ip)
    return _issue_login_tokens(
        db=db,
        request=request,
        response=response,
        user=user,
        ip=ip,
        user_agent=_request_user_agent(request),
    )


@router.get("/mfa/status", response_model=MfaStatusOut)
def mfa_status(db: DbSession, current_user: CurrentUser) -> MfaStatusOut:
    return MfaStatusOut(
        enabled=mfa_service.is_mfa_enabled(db, user_id=current_user.id),
        required=mfa_service.mfa_required_for_user(db, current_user),
        setup_required=mfa_service.setup_required_for_user(db, current_user),
    )


@router.post("/mfa/setup", response_model=MfaSetupOut, dependencies=[Depends(set_mutation_cache_control)])
def mfa_setup(
    request: Request,
    db: DbSession,
    body: MfaSetupIn,
    current_user: OptionalUser,
) -> MfaSetupOut:
    user = current_user
    if user is None and body.mfa_challenge_token:
        challenge = mfa_service.decode_challenge(body.mfa_challenge_token)
        if challenge is None or not challenge.setup_required:
            raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401)
        user = user_repository.get_by_id(db, challenge.user_id)
    if user is None or not user.is_active:
        raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401)
    setup = mfa_service.build_setup(db, user=user)
    mfa_service.audit_mfa_event(
        event_type="auth.mfa.setup_started",
        user=user,
        ip_address=resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR),
    )
    return MfaSetupOut(secret=setup.secret, otpauth_uri=setup.otpauth_uri)


@router.post("/mfa/enable", response_model=MfaEnableOut, dependencies=[Depends(set_mutation_cache_control)])
def mfa_enable(request: Request, db: DbSession, body: MfaEnableIn, current_user: OptionalUser) -> MfaEnableOut:
    user = current_user
    if user is None and body.mfa_challenge_token:
        challenge = mfa_service.decode_challenge(body.mfa_challenge_token)
        if challenge is None or not challenge.setup_required:
            raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401)
        user = user_repository.get_by_id(db, challenge.user_id)
    if user is None or not user.is_active:
        raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401)
    ok, retry_after = auth_rate_limit.try_consume_mfa_attempt(
        challenge_token=body.mfa_challenge_token or f"enable:{user.id}",
        client_ip=resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR),
        user_id=str(user.id),
    )
    if not ok:
        raise AuthRateLimitExceeded(retry_after=retry_after)
    try:
        codes = mfa_service.enable_mfa(db, user=user, code=body.code)
    except ValueError:
        raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401, code=mfa_service.MFA_INVALID_CODE)
    mfa_service.audit_mfa_event(
        event_type="auth.mfa.enabled",
        user=user,
        ip_address=resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR),
    )
    return MfaEnableOut(recovery_codes=codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(set_mutation_cache_control)])
def mfa_disable(request: Request, db: DbSession, body: MfaDisableIn, current_user: CurrentUser) -> Response:
    if not mfa_service.verify_user_mfa(db, user=current_user, code=body.code):
        raise AppError(refresh_token_service.AUTH_FAILED_MESSAGE, status_code=401, code=mfa_service.MFA_INVALID_CODE)
    try:
        mfa_service.disable_mfa(db, user=current_user)
    except ValueError:
        raise AppError("管理员必须开启 MFA", status_code=400, code="ADMIN_MFA_REQUIRED")
    mfa_service.audit_mfa_event(
        event_type="auth.mfa.disabled",
        user=current_user,
        ip_address=resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=Token, dependencies=[Depends(set_mutation_cache_control)])
def refresh_access_token(request: Request, response: Response, db: DbSession) -> Token:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    verify_csrf_request(request)
    raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    user, issued_refresh = refresh_token_service.rotate_refresh_token(
        db,
        raw_token=raw,
        ip_address=ip,
        user_agent=_request_user_agent(request),
        request_id=_request_id(request),
    )
    access_token = auth_service.issue_token_for_user(user)
    _set_refresh_cookie(response, issued_refresh.raw_token)
    _set_csrf_cookie(response)
    return Token(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(set_mutation_cache_control)])
def logout(request: Request, response: Response, db: DbSession) -> Response:
    ip = resolved_client_ip(request, trust_x_forwarded_for=settings.AUTH_TRUST_X_FORWARDED_FOR)
    verify_csrf_request(request)
    refresh_token_service.delete_refresh_token(
        db,
        raw_token=request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME),
        ip_address=ip,
        request_id=_request_id(request),
        user_agent=_request_user_agent(request),
    )
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/sessions", response_model=AuthSessionsOut)
def list_sessions(request: Request, db: DbSession, current_user: CurrentUser) -> AuthSessionsOut:
    rows = refresh_token_service.active_sessions(
        db,
        user=current_user,
        current_raw_token=request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME),
    )
    return AuthSessionsOut(sessions=rows)


@router.post(
    "/sessions/revoke-others",
    response_model=RevokeOtherSessionsOut,
    dependencies=[Depends(set_mutation_cache_control)],
)
def revoke_other_sessions(request: Request, db: DbSession, current_user: CurrentUser) -> RevokeOtherSessionsOut:
    verify_csrf_request(request)
    n = refresh_token_service.revoke_other_sessions(
        db,
        user=current_user,
        current_raw_token=request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME),
    )
    return RevokeOtherSessionsOut(revoked_count=n)


@router.post(
    "/sessions/{session_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(set_mutation_cache_control)],
)
def revoke_session(
    session_id: UUID,
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    verify_csrf_request(request)
    revoked_current = refresh_token_service.revoke_session(
        db,
        user=current_user,
        token_id=session_id,
        current_raw_token=request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME),
    )
    if revoked_current:
        _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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
