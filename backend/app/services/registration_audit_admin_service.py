from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import registration_attempt_repository
from app.schemas.invite_codes import AdminRegistrationAttemptItem, AdminRegistrationAttemptListOut


def list_registration_attempts(db: Session, *, offset: int, limit: int) -> AdminRegistrationAttemptListOut:
    rows, total = registration_attempt_repository.list_registration_attempts(db, offset=offset, limit=limit)
    return AdminRegistrationAttemptListOut(
        items=[AdminRegistrationAttemptItem.model_validate(r) for r in rows],
        total=total,
    )
