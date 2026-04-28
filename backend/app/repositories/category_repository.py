from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.taxonomy_text import normalize_taxonomy_name_lookup
from app.models.category import Category


def list_all(
    db: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Category]:
    """按 (name, id) 升序列出。`limit` 为 None 时不加 LIMIT；此时忽略 `offset`。"""
    stmt = select(Category).order_by(Category.name.asc(), Category.id.asc())
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_after(
    db: Session,
    *,
    after_name: str,
    after_id: uuid.UUID,
    limit: int,
) -> list[Category]:
    """键集分页：返回严格大于 (after_name, after_id) 的记录。"""
    stmt = (
        select(Category)
        .where(
            or_(
                Category.name > after_name,
                and_(Category.name == after_name, Category.id > after_id),
            )
        )
        .order_by(Category.name.asc(), Category.id.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, category_id: uuid.UUID) -> Category | None:
    stmt = select(Category).where(Category.id == category_id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_name(db: Session, name: str) -> Category | None:
    key = normalize_taxonomy_name_lookup(name)
    stmt = select(Category).where(func.lower(Category.name) == key)
    return db.execute(stmt).scalar_one_or_none()


def get_by_name_excluding_id(db: Session, name: str, exclude_id: uuid.UUID) -> Category | None:
    key = normalize_taxonomy_name_lookup(name)
    stmt = select(Category).where(
        func.lower(Category.name) == key,
        Category.id != exclude_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def create(db: Session, *, name: str, description: str | None) -> Category:
    row = Category(name=name, description=description)
    db.add(row)
    db.flush()
    return row


def delete(db: Session, row: Category) -> None:
    db.delete(row)
    db.flush()
