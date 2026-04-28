from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.user_privacy import UserPrivacySetting


def get(db: Session, *, user_id: uuid.UUID) -> UserPrivacySetting | None:
    return db.get(UserPrivacySetting, user_id)


def get_or_create(db: Session, *, user_id: uuid.UUID) -> UserPrivacySetting:
    row = get(db, user_id=user_id)
    if row is not None:
        return row
    row = UserPrivacySetting(user_id=user_id)
    db.add(row)
    db.flush()
    return row
