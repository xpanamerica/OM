from __future__ import annotations

import logging
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.security_event import SecurityEvent

_log = logging.getLogger("app.security_events")


def insert_event_sync(
    *,
    event_type: str,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    subject_hash: str | None = None,
    detail: str | None = None,
    extra: str | None = None,
    request_id: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """独立会话写入，避免主请求事务回滚导致事件丢失。"""
    row = SecurityEvent(
        event_type=event_type[:64],
        user_id=user_id,
        ip_address=(ip_address[:64] if ip_address else None),
        subject_hash=(subject_hash[:64] if subject_hash else None),
        detail=(detail[:256] if detail else None),
        extra=extra,
        request_id=(request_id[:64] if request_id else None),
        user_agent=(user_agent[:512] if user_agent else None),
        metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True) if metadata else None,
    )
    try:
        with SessionLocal() as db:
            db.add(row)
            db.commit()
    except Exception:
        _log.exception("security_event_persist_failed type=%s", event_type)


def insert_event(
    db: Session,
    *,
    event_type: str,
    ip_address: str | None,
    subject_hash: str | None,
    detail: str | None,
    user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """同一请求会话内写入（测试或需与业务同事务时使用）。"""
    db.add(
        SecurityEvent(
            event_type=event_type[:64],
            user_id=user_id,
            ip_address=(ip_address[:64] if ip_address else None),
            subject_hash=(subject_hash[:64] if subject_hash else None),
            detail=(detail[:256] if detail else None),
            request_id=(request_id[:64] if request_id else None),
            user_agent=(user_agent[:512] if user_agent else None),
            metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True) if metadata else None,
        )
    )
