from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_friend_request import UserFriendRequest


def get_by_id(db: Session, request_id: uuid.UUID) -> UserFriendRequest | None:
    return db.get(UserFriendRequest, request_id)


def find_pending_between(db: Session, *, user_a: uuid.UUID, user_b: uuid.UUID) -> UserFriendRequest | None:
    stmt = (
        select(UserFriendRequest)
        .where(
            UserFriendRequest.status == "pending",
            or_(
                (UserFriendRequest.requester_id == user_a) & (UserFriendRequest.recipient_id == user_b),
                (UserFriendRequest.requester_id == user_b) & (UserFriendRequest.recipient_id == user_a),
            ),
        )
        .order_by(UserFriendRequest.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    requester_id: uuid.UUID,
    recipient_id: uuid.UUID,
    message: str | None,
) -> UserFriendRequest:
    row = UserFriendRequest(requester_id=requester_id, recipient_id=recipient_id, message=message)
    db.add(row)
    db.flush()
    return row


def list_incoming(
    db: Session,
    *,
    recipient_id: uuid.UUID,
    status: str,
    offset: int,
    limit: int,
) -> list[tuple[UserFriendRequest, User]]:
    stmt = (
        select(UserFriendRequest, User)
        .join(User, User.id == UserFriendRequest.requester_id)
        .where(UserFriendRequest.recipient_id == recipient_id, UserFriendRequest.status == status, User.deleted_at.is_(None))
        .order_by(UserFriendRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(r, u) for r, u in db.execute(stmt).all()]


def list_outgoing(
    db: Session,
    *,
    requester_id: uuid.UUID,
    status: str,
    offset: int,
    limit: int,
) -> list[tuple[UserFriendRequest, User]]:
    stmt = (
        select(UserFriendRequest, User)
        .join(User, User.id == UserFriendRequest.recipient_id)
        .where(UserFriendRequest.requester_id == requester_id, UserFriendRequest.status == status, User.deleted_at.is_(None))
        .order_by(UserFriendRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(r, u) for r, u in db.execute(stmt).all()]


def count_pending_incoming(db: Session, *, recipient_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(UserFriendRequest).where(
        UserFriendRequest.recipient_id == recipient_id,
        UserFriendRequest.status == "pending",
    )
    return int(db.execute(stmt).scalar_one())
