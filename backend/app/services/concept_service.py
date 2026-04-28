"""概念节点与视频—概念绑定（管理员维护）。"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.knowledge_codes import (
    CONCEPT_NAME_CONFLICT,
    CONCEPT_NOT_FOUND,
    VIDEO_CONCEPT_DUPLICATE_IN_PAYLOAD,
    VIDEO_CONCEPT_TIME_RANGE_INVALID,
)
from app.core.video_codes import VIDEO_NOT_FOUND
from app.models.concept import Concept
from app.models.user import User
from app.repositories import concept_repository, video_concept_repository, video_repository
from app.schemas.concept import ConceptCreate, ConceptLinkedVideoOut, ConceptUpdate, VideoConceptsPut
from app.services import video_privacy, video_service


def _get_concept_or_404(db: Session, concept_id: uuid.UUID) -> Concept:
    row = concept_repository.get_by_id(db, concept_id)
    if row is None:
        raise AppError("概念不存在", status_code=404, code=CONCEPT_NOT_FOUND)
    return row


def list_concepts(db: Session, *, offset: int, limit: int) -> tuple[list[Concept], int]:
    total = concept_repository.count_all(db)
    rows = concept_repository.list_concepts(db, offset=offset, limit=limit)
    return rows, total


def get_concept_public(db: Session, concept_id: uuid.UUID) -> Concept:
    """公开只读：按主键取概念，不存在则 404。"""
    return _get_concept_or_404(db, concept_id)


def list_published_videos_for_concept(
    db: Session,
    viewer: User | None,
    concept_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
) -> tuple[list[ConceptLinkedVideoOut], int]:
    """概念下已发布且已绑定的视频（公开列表；脱敏与 ``VideoListItem`` 一致，并附带片段时间）。"""
    _get_concept_or_404(db, concept_id)
    total = video_concept_repository.count_published_videos_for_concept(db, concept_id=concept_id)
    pairs = video_concept_repository.list_published_videos_for_concept(
        db, concept_id=concept_id, offset=offset, limit=limit
    )
    items: list[ConceptLinkedVideoOut] = []
    for v, vc in pairs:
        base = video_privacy.video_list_item_for_viewer(v, viewer, db)
        items.append(
            ConceptLinkedVideoOut(
                **base.model_dump(),
                start_time_seconds=vc.start_time_seconds,
                end_time_seconds=vc.end_time_seconds,
            )
        )
    return items, total


def create_concept(db: Session, payload: ConceptCreate) -> Concept:
    if concept_repository.get_by_name_normalized(db, payload.name):
        raise AppError("概念名称已存在", status_code=409, code=CONCEPT_NAME_CONFLICT)
    row = concept_repository.create(db, name=payload.name, description=payload.description)
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError:
        db.rollback()
        raise AppError("概念名称已存在", status_code=409, code=CONCEPT_NAME_CONFLICT) from None
    return row


def update_concept(db: Session, concept_id: uuid.UUID, payload: ConceptUpdate) -> Concept:
    row = _get_concept_or_404(db, concept_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        conflict = concept_repository.get_by_name_normalized_excluding(db, data["name"], concept_id)
        if conflict is not None:
            raise AppError("概念名称已存在", status_code=409, code=CONCEPT_NAME_CONFLICT)
        row.name = data["name"]
    if "description" in data:
        row.description = data["description"]
    if not data:
        return row
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError:
        db.rollback()
        raise AppError("概念名称已存在", status_code=409, code=CONCEPT_NAME_CONFLICT) from None
    return row


def _validate_time_pair(start: int | None, end: int | None) -> None:
    if start is not None and end is not None and end < start:
        raise AppError(
            "结束时间不能早于开始时间",
            status_code=400,
            code=VIDEO_CONCEPT_TIME_RANGE_INVALID,
        )


def replace_video_concepts(db: Session, video_id: uuid.UUID, payload: VideoConceptsPut) -> None:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    seen: set[uuid.UUID] = set()
    links: list[tuple[uuid.UUID, int | None, int | None]] = []
    for it in payload.items:
        if it.concept_id in seen:
            raise AppError("同一概念不能重复绑定", status_code=400, code=VIDEO_CONCEPT_DUPLICATE_IN_PAYLOAD)
        seen.add(it.concept_id)
        _validate_time_pair(it.start_time_seconds, it.end_time_seconds)
        if concept_repository.get_by_id(db, it.concept_id) is None:
            raise AppError("概念不存在", status_code=404, code=CONCEPT_NOT_FOUND)
        links.append((it.concept_id, it.start_time_seconds, it.end_time_seconds))
    video_concept_repository.replace_for_video(db, video_id, links=links)
    db.commit()


def list_concepts_for_video(db: Session, viewer: User | None, video_id: uuid.UUID):
    """需能查看该视频（与详情可见性一致）。"""
    video_service.get_video(db, video_id, viewer)
    pairs = video_concept_repository.list_for_video(db, video_id)
    return pairs
