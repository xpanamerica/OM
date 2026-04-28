"""学习路径：创建者为登录用户；编辑为创建者或管理员。"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.knowledge_codes import (
    LEARNING_PATH_FORBIDDEN,
    LEARNING_PATH_ITEMS_ORDER_CONFLICT,
    LEARNING_PATH_NOT_FOUND,
    LEARNING_PATH_PUBLISH_REQUIRES_PUBLISHED_VIDEOS,
)
from app.core.video_codes import VIDEO_NOT_FOUND
from app.models.enums import UserRole, VideoStatus
from app.models.learning_path import LearningPath
from app.models.user import User
from app.repositories import learning_path_repository, video_repository
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathDetail,
    LearningPathItemPublic,
    LearningPathItemsPut,
    LearningPathPublic,
    LearningPathUpdate,
)
from app.services import video_privacy, video_service


def _path_or_404(db: Session, path_id: uuid.UUID) -> LearningPath:
    row = learning_path_repository.get_by_id(db, path_id)
    if row is None:
        raise AppError("学习路径不存在", status_code=404, code=LEARNING_PATH_NOT_FOUND)
    return row


def can_view_path(path: LearningPath, viewer: User | None) -> bool:
    if path.is_published:
        return True
    if viewer is None:
        return False
    if viewer.role == UserRole.ADMIN:
        return True
    return path.creator_id == viewer.id


def assert_can_edit_path(path: LearningPath, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if path.creator_id == actor.id:
        return
    raise AppError("无权修改该学习路径", status_code=403, code=LEARNING_PATH_FORBIDDEN)


def _assert_order_indices_unique(items: list) -> None:
    orders = [it.order_index for it in items]
    if len(orders) != len(set(orders)):
        raise AppError("顺序序号不能重复", status_code=400, code=LEARNING_PATH_ITEMS_ORDER_CONFLICT)


def _assert_videos_exist(db: Session, video_ids: list[uuid.UUID]) -> None:
    for vid in video_ids:
        if video_repository.get_by_id(db, vid, load_tags=False) is None:
            raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)


def _assert_all_videos_published(db: Session, video_ids: list[uuid.UUID]) -> None:
    for vid in video_ids:
        v = video_repository.get_by_id(db, vid, load_tags=False)
        if v is None or v.status != VideoStatus.PUBLISHED:
            raise AppError(
                "发布路径要求所含视频均为已发布状态",
                status_code=400,
                code=LEARNING_PATH_PUBLISH_REQUIRES_PUBLISHED_VIDEOS,
            )


def _items_tuples_from_write(items: list) -> list[tuple[int, uuid.UUID, str | None]]:
    return [(it.order_index, it.video_id, it.note) for it in items]


def create_path(db: Session, actor: User, payload: LearningPathCreate) -> LearningPath:
    _assert_order_indices_unique(payload.items)
    vids = [it.video_id for it in payload.items]
    _assert_videos_exist(db, vids)
    if payload.is_published:
        _assert_all_videos_published(db, vids)
    row = learning_path_repository.create(
        db,
        title=payload.title,
        description=payload.description,
        creator_id=actor.id,
        is_published=payload.is_published,
    )
    if payload.items:
        learning_path_repository.replace_items(db, row.id, items=_items_tuples_from_write(payload.items))
    db.commit()
    db.refresh(row)
    return row


def update_path(db: Session, actor: User, path_id: uuid.UUID, payload: LearningPathUpdate) -> LearningPath:
    row = _path_or_404(db, path_id)
    assert_can_edit_path(row, actor)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        row.title = data["title"]
    if "description" in data:
        row.description = data["description"]
    if "is_published" in data and data["is_published"] is not None:
        row.is_published = bool(data["is_published"])
    if row.is_published:
        items = learning_path_repository.list_items(db, path_id)
        _assert_all_videos_published(db, [it.video_id for it in items])
    db.commit()
    db.refresh(row)
    return row


def replace_path_items(db: Session, actor: User, path_id: uuid.UUID, payload: LearningPathItemsPut) -> None:
    row = _path_or_404(db, path_id)
    assert_can_edit_path(row, actor)
    _assert_order_indices_unique(payload.items)
    vids = [it.video_id for it in payload.items]
    _assert_videos_exist(db, vids)
    if row.is_published:
        _assert_all_videos_published(db, vids)
    learning_path_repository.replace_items(db, path_id, items=_items_tuples_from_write(payload.items))
    db.commit()


def list_paths(db: Session, viewer: User | None, *, offset: int, limit: int) -> tuple[list[LearningPath], int]:
    return learning_path_repository.list_paths(db, viewer=viewer, offset=offset, limit=limit)


def get_path_detail(db: Session, viewer: User | None, path_id: uuid.UUID) -> LearningPathDetail:
    row = _path_or_404(db, path_id)
    if not can_view_path(row, viewer):
        raise AppError("学习路径不存在", status_code=404, code=LEARNING_PATH_NOT_FOUND)
    items = learning_path_repository.list_items(db, path_id)
    out_items: list[LearningPathItemPublic] = []
    for it in items:
        v = video_repository.get_by_id(db, it.video_id, load_tags=True)
        video_pub = None
        if v is not None and video_service.can_view_video(v, viewer):
            video_pub = video_privacy.video_list_item_for_viewer(v, viewer, db)
        out_items.append(
            LearningPathItemPublic(
                order_index=it.order_index,
                video_id=it.video_id,
                note=it.note,
                video=video_pub,
            )
        )
    base = LearningPathPublic.model_validate(row)
    return LearningPathDetail(**base.model_dump(), items=out_items)
