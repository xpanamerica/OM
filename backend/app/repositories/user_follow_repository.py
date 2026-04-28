from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_follow import UserFollow


def count_following(db: Session, *, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(UserFollow).where(UserFollow.follower_id == user_id)
    return int(db.execute(stmt).scalar_one())


def count_followers(db: Session, *, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(UserFollow).where(UserFollow.followee_id == user_id)
    return int(db.execute(stmt).scalar_one())


def exists(db: Session, *, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
    stmt = select(func.count()).select_from(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    return int(db.execute(stmt).scalar_one()) > 0


def create(db: Session, *, follower_id: uuid.UUID, followee_id: uuid.UUID) -> UserFollow:
    row = UserFollow(follower_id=follower_id, followee_id=followee_id)
    db.add(row)
    db.flush()
    return row


def delete_pair(db: Session, *, follower_id: uuid.UUID, followee_id: uuid.UUID) -> int:
    stmt = delete(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    res = db.execute(stmt)
    return int(res.rowcount or 0)


def list_following(db: Session, *, user_id: uuid.UUID, offset: int, limit: int) -> list[tuple[User, UserFollow]]:
    stmt = (
        select(User, UserFollow)
        .join(UserFollow, User.id == UserFollow.followee_id)
        .where(UserFollow.follower_id == user_id, User.deleted_at.is_(None))
        .order_by(UserFollow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(u, f) for u, f in db.execute(stmt).all()]


def list_followers(db: Session, *, user_id: uuid.UUID, offset: int, limit: int) -> list[tuple[User, UserFollow]]:
    stmt = (
        select(User, UserFollow)
        .join(UserFollow, User.id == UserFollow.follower_id)
        .where(UserFollow.followee_id == user_id, User.deleted_at.is_(None))
        .order_by(UserFollow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(u, f) for u, f in db.execute(stmt).all()]


def list_mutual_friends(db: Session, *, user_id: uuid.UUID, offset: int, limit: int) -> list[tuple[User, UserFollow]]:
    peer_follow = UserFollow.__table__.alias("peer_follow")
    stmt = (
        select(User, UserFollow)
        .join(UserFollow, User.id == UserFollow.followee_id)
        .join(
            peer_follow,
            (peer_follow.c.follower_id == User.id) & (peer_follow.c.followee_id == user_id),
        )
        .where(UserFollow.follower_id == user_id, User.deleted_at.is_(None))
        .order_by(UserFollow.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [(u, f) for u, f in db.execute(stmt).all()]


def count_mutual_friends(db: Session, *, user_id: uuid.UUID) -> int:
    peer_follow = UserFollow.__table__.alias("peer_follow")
    stmt = (
        select(func.count())
        .select_from(UserFollow)
        .join(
            peer_follow,
            (peer_follow.c.follower_id == UserFollow.followee_id) & (peer_follow.c.followee_id == user_id),
        )
        .where(UserFollow.follower_id == user_id)
    )
    return int(db.execute(stmt).scalar_one())
