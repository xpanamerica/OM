from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.taxonomy_text import normalize_taxonomy_name_lookup
from app.models.concept import Concept


def get_by_id(db: Session, concept_id: uuid.UUID) -> Concept | None:
    return db.execute(select(Concept).where(Concept.id == concept_id)).scalar_one_or_none()


def get_by_name_normalized(db: Session, name: str) -> Concept | None:
    key = normalize_taxonomy_name_lookup(name)
    stmt = select(Concept).where(func.lower(Concept.name) == key)
    return db.execute(stmt).scalar_one_or_none()


def get_by_name_normalized_excluding(db: Session, name: str, exclude_id: uuid.UUID) -> Concept | None:
    key = normalize_taxonomy_name_lookup(name)
    stmt = select(Concept).where(func.lower(Concept.name) == key, Concept.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none()


def count_all(db: Session) -> int:
    return int(db.scalar(select(func.count(Concept.id))) or 0)


def list_concepts(
    db: Session,
    *,
    offset: int,
    limit: int,
) -> list[Concept]:
    stmt = (
        select(Concept).order_by(Concept.name.asc(), Concept.id.asc()).offset(offset).limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def create(db: Session, *, name: str, description: str | None) -> Concept:
    row = Concept(name=name, description=description)
    db.add(row)
    db.flush()
    return row
