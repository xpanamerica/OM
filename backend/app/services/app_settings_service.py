from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import app_setting_repository
from app.schemas.admin_management import AdminPlatformSettingsOut, AdminPlatformSettingsUpdate

VIDEO_PUBLISH_WITHOUT_REVIEW_KEY = "video_publish_without_review_enabled"
REGISTRATION_INVITE_CODE_REQUIRED_KEY = "registration_invite_code_required"


def _bool_to_value(value: bool) -> str:
    return "true" if value else "false"


def _value_to_bool(value: str | None) -> bool:
    return (value or "false").strip().lower() == "true"


def is_video_publish_without_review_enabled(db: Session) -> bool:
    return _value_to_bool(app_setting_repository.get_value(db, key=VIDEO_PUBLISH_WITHOUT_REVIEW_KEY))


def is_registration_invite_code_required(db: Session) -> bool:
    return _value_to_bool(app_setting_repository.get_value(db, key=REGISTRATION_INVITE_CODE_REQUIRED_KEY))


def get_admin_platform_settings(db: Session) -> AdminPlatformSettingsOut:
    return AdminPlatformSettingsOut(
        video_publish_without_review_enabled=is_video_publish_without_review_enabled(db),
        registration_invite_code_required=is_registration_invite_code_required(db),
    )


def update_admin_platform_settings(
    db: Session, payload: AdminPlatformSettingsUpdate
) -> AdminPlatformSettingsOut:
    if payload.video_publish_without_review_enabled is not None:
        app_setting_repository.set_value(
            db,
            key=VIDEO_PUBLISH_WITHOUT_REVIEW_KEY,
            value=_bool_to_value(payload.video_publish_without_review_enabled),
        )
    if payload.registration_invite_code_required is not None:
        app_setting_repository.set_value(
            db,
            key=REGISTRATION_INVITE_CODE_REQUIRED_KEY,
            value=_bool_to_value(payload.registration_invite_code_required),
        )
    db.commit()
    return get_admin_platform_settings(db)
