from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.direct_message import DirectConversation, DirectMessage
from app.models.user import User


def sorted_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def get_conversation_between(db: Session, *, user_a: uuid.UUID, user_b: uuid.UUID) -> DirectConversation | None:
    low, high = sorted_pair(user_a, user_b)
    stmt = select(DirectConversation).where(
        DirectConversation.participant_low_id == low,
        DirectConversation.participant_high_id == high,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_or_create_conversation(db: Session, *, user_a: uuid.UUID, user_b: uuid.UUID) -> DirectConversation:
    row = get_conversation_between(db, user_a=user_a, user_b=user_b)
    if row is not None:
        return row
    low, high = sorted_pair(user_a, user_b)
    row = DirectConversation(participant_low_id=low, participant_high_id=high)
    db.add(row)
    db.flush()
    return row


def add_message(
    db: Session,
    *,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    recipient_id: uuid.UUID,
    body: str,
) -> DirectMessage:
    msg = DirectMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
        body=body,
    )
    db.add(msg)
    db.flush()
    conv = db.get(DirectConversation, conversation_id)
    if conv is not None:
        conv.last_message_at = msg.created_at
        db.add(conv)
    db.flush()
    return msg


def list_messages(db: Session, *, conversation_id: uuid.UUID, offset: int, limit: int) -> list[DirectMessage]:
    stmt = (
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation_id)
        .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def mark_read_from_peer(db: Session, *, conversation_id: uuid.UUID, recipient_id: uuid.UUID) -> int:
    stmt = (
        update(DirectMessage)
        .where(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.recipient_id == recipient_id,
            DirectMessage.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    res = db.execute(stmt)
    return int(res.rowcount or 0)


def unread_count(db: Session, *, conversation_id: uuid.UUID, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(DirectMessage).where(
        DirectMessage.conversation_id == conversation_id,
        DirectMessage.recipient_id == user_id,
        DirectMessage.read_at.is_(None),
    )
    return int(db.execute(stmt).scalar_one())


def last_message(db: Session, *, conversation_id: uuid.UUID) -> DirectMessage | None:
    stmt = (
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation_id)
        .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_conversations_for_user(
    db: Session, *, user_id: uuid.UUID, offset: int, limit: int
) -> list[tuple[DirectConversation, User]]:
    stmt = (
        select(DirectConversation, User)
        .join(
            User,
            or_(
                (DirectConversation.participant_low_id == user_id)
                & (User.id == DirectConversation.participant_high_id),
                (DirectConversation.participant_high_id == user_id)
                & (User.id == DirectConversation.participant_low_id),
            ),
        )
        .where(
            or_(
                DirectConversation.participant_low_id == user_id,
                DirectConversation.participant_high_id == user_id,
            ),
            User.deleted_at.is_(None),
        )
        .order_by(DirectConversation.last_message_at.desc().nullslast(), DirectConversation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(c, u) for c, u in db.execute(stmt).all()]
