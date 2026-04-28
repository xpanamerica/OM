from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.tag import Tag


def list_all(
    db: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Tag]:
    """按 (name, id) 升序列出。`limit` 为 None 时不加 LIMIT；此时忽略 `offset`。"""
    stmt = select(Tag).order_by(Tag.name.asc(), Tag.id.asc())
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_after(
    db: Session,
    *,
    after_name: str,
    after_id: uuid.UUID,
    limit: int,
) -> list[Tag]:
    stmt = (
        select(Tag)
        .where(
            or_(
                Tag.name > after_name,
                and_(Tag.name == after_name, Tag.id > after_id),
            )
        )
        .order_by(Tag.name.asc(), Tag.id.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, tag_id: uuid.UUID) -> Tag | None:
    stmt = select(Tag).where(Tag.id == tag_id)
    return db.execute(stmt).scalar_one_or_none()


def list_by_ids(db: Session, ids: list[uuid.UUID]) -> list[Tag]:
    """按主键批量加载；用于视频标签校验（本阶段为视频模块新增，不改变既有标签 API 行为）。"""
    if not ids:
        return []
    stmt = select(Tag).where(Tag.id.in_(ids))
    return list(db.execute(stmt).scalars().all())


def get_by_name(db: Session, name: str) -> Tag | None:
    stmt = select(Tag).where(func.lower(Tag.name) == name.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_by_name_excluding_id(db: Session, name: str, exclude_id: uuid.UUID) -> Tag | None:
    stmt = select(Tag).where(
        func.lower(Tag.name) == name.lower(),
        Tag.id != exclude_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def create(db: Session, *, name: str) -> Tag:
    row = Tag(name=name)
    db.add(row)
    db.flush()
    return row


def delete(db: Session, row: Tag) -> None:
    db.delete(row)
    db.flush()
