"""视频表统计字段原子更新（阶段 10.1）。

``likes_count`` / ``favorites_count`` / ``views_count`` 的增减仅在此模块以单条 ``UPDATE`` 完成，
避免 ORM 读改写并发丢失；结果统一 ``>= 0``。业务事务仍由调用方 ``service`` 持有 ``Session`` 提交。

调用关系：``video_interaction_service``、``view_record_service``。
"""

from __future__ import annotations

import uuid

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from app.models.video import Video


def adjust_likes_count(db: Session, *, video_id: uuid.UUID, delta: int) -> None:
    """原子调整 ``likes_count``；``delta`` 仅 ``-1`` / ``0`` / ``+1``；结果不低于 0。"""
    d = int(delta)
    if d not in (-1, 0, 1):
        raise ValueError("likes_count 仅支持 delta 为 -1、0 或 +1")
    if d == 0:
        return
    new_c = Video.likes_count + d
    db.execute(
        update(Video)
        .where(Video.id == video_id)
        .values(likes_count=case((new_c < 0, 0), else_=new_c))
    )
    v = db.get(Video, video_id)
    if v is not None:
        db.expire(v, ["likes_count"])
    db.flush()


def adjust_favorites_count(db: Session, *, video_id: uuid.UUID, delta: int) -> None:
    """原子调整 ``favorites_count``；``delta`` 仅 ``-1`` / ``0`` / ``+1``；结果不低于 0。"""
    d = int(delta)
    if d not in (-1, 0, 1):
        raise ValueError("favorites_count 仅支持 delta 为 -1、0 或 +1")
    if d == 0:
        return
    new_c = Video.favorites_count + d
    db.execute(
        update(Video)
        .where(Video.id == video_id)
        .values(favorites_count=case((new_c < 0, 0), else_=new_c))
    )
    v = db.get(Video, video_id)
    if v is not None:
        db.expire(v, ["favorites_count"])
    db.flush()


def increment_views_count(db: Session, *, video_id: uuid.UUID) -> None:
    """原子 ``views_count + 1``；结果钳制为不低于 0（防御历史脏数据）。"""
    d = 1
    new_c = Video.views_count + d
    db.execute(
        update(Video)
        .where(Video.id == video_id)
        .values(views_count=case((new_c < 0, 0), else_=new_c))
    )
    v = db.get(Video, video_id)
    if v is not None:
        db.expire(v, ["views_count"])
    db.flush()
