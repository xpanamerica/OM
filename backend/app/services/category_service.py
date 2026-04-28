from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.category import Category
from app.repositories import category_repository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.persist import commit_refresh_or_conflict
from app.services.taxonomy_list import run_taxonomy_list


def list_categories(
    db: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
    cursor: str | None = None,
) -> tuple[list[Category], bool]:
    return run_taxonomy_list(
        db,
        fetch_all=category_repository.list_all,
        fetch_after=category_repository.list_after,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )


def create_category(db: Session, payload: CategoryCreate) -> Category:
    if category_repository.get_by_name(db, payload.name):
        raise AppError("分类名称已存在", status_code=409)
    row = category_repository.create(db, name=payload.name, description=payload.description)
    return commit_refresh_or_conflict(db, row, conflict_message="分类名称已存在")


def _get_or_404(db: Session, category_id: uuid.UUID) -> Category:
    row = category_repository.get_by_id(db, category_id)
    if row is None:
        raise AppError("分类不存在", status_code=404)
    return row


def update_category(db: Session, category_id: uuid.UUID, payload: CategoryUpdate) -> Category:
    row = _get_or_404(db, category_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        conflict = category_repository.get_by_name_excluding_id(db, data["name"], category_id)
        if conflict is not None:
            raise AppError("分类名称已存在", status_code=409)
        row.name = data["name"]
    if "description" in data:
        row.description = data["description"]
    if not data:
        return row
    return commit_refresh_or_conflict(db, row, conflict_message="分类名称已存在")


def delete_category(db: Session, category_id: uuid.UUID) -> None:
    row = _get_or_404(db, category_id)
    category_repository.delete(db, row)
    db.commit()
