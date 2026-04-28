"""数据库提交与完整性错误映射（供各 service 复用）。"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError

T = TypeVar("T")


def commit_refresh_or_conflict(db: Session, row: T, *, conflict_message: str) -> T:
    """提交并刷新 ORM 行；遇唯一约束等完整性错误时回滚并抛出 409。"""
    try:
        db.commit()
        db.refresh(row)
    except IntegrityError:
        db.rollback()
        raise AppError(conflict_message, status_code=409) from None
    return row
