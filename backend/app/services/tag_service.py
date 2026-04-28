from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.tag import Tag
from app.repositories import tag_repository
from app.schemas.tag import TagCreate, TagUpdate
from app.services.persist import commit_refresh_or_conflict
from app.services.taxonomy_list import run_taxonomy_list


def list_tags(
    db: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
    cursor: str | None = None,
) -> tuple[list[Tag], bool]:
    return run_taxonomy_list(
        db,
        fetch_all=tag_repository.list_all,
        fetch_after=tag_repository.list_after,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )


def create_tag(db: Session, payload: TagCreate) -> Tag:
    if tag_repository.get_by_name(db, payload.name):
        raise AppError("标签名称已存在", status_code=409)
    row = tag_repository.create(db, name=payload.name)
    return commit_refresh_or_conflict(db, row, conflict_message="标签名称已存在")


def _get_or_404(db: Session, tag_id: uuid.UUID) -> Tag:
    row = tag_repository.get_by_id(db, tag_id)
    if row is None:
        raise AppError("标签不存在", status_code=404)
    return row


def update_tag(db: Session, tag_id: uuid.UUID, payload: TagUpdate) -> Tag:
    row = _get_or_404(db, tag_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        conflict = tag_repository.get_by_name_excluding_id(db, data["name"], tag_id)
        if conflict is not None:
            raise AppError("标签名称已存在", status_code=409)
        row.name = data["name"]
    if not data:
        return row
    return commit_refresh_or_conflict(db, row, conflict_message="标签名称已存在")


def delete_tag(db: Session, tag_id: uuid.UUID) -> None:
    row = _get_or_404(db, tag_id)
    tag_repository.delete(db, row)
    db.commit()
