from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.security_event import SecurityEvent

_log = logging.getLogger("app.security_events")


def insert_event_sync(
    *,
    event_type: str,
    ip_address: str | None = None,
    subject_hash: str | None = None,
    detail: str | None = None,
    extra: str | None = None,
) -> None:
    """独立会话写入，避免主请求事务回滚导致事件丢失。"""
    row = SecurityEvent(
        event_type=event_type[:64],
        ip_address=(ip_address[:64] if ip_address else None),
        subject_hash=(subject_hash[:64] if subject_hash else None),
        detail=(detail[:256] if detail else None),
        extra=extra,
    )
    try:
        with SessionLocal() as db:
            db.add(row)
            db.commit()
    except Exception:
        _log.exception("security_event_persist_failed type=%s", event_type)


def insert_event(db: Session, *, event_type: str, ip_address: str | None, subject_hash: str | None, detail: str | None) -> None:
    """同一请求会话内写入（测试或需与业务同事务时使用）。"""
    db.add(
        SecurityEvent(
            event_type=event_type[:64],
            ip_address=(ip_address[:64] if ip_address else None),
            subject_hash=(subject_hash[:64] if subject_hash else None),
            detail=(detail[:256] if detail else None),
        )
    )
