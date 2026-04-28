"""工作流审计的可观测日志。

- 成功落库：``event=workflow_audit``（INFO），可按 event / video_id 检索。
- 序号重试：``event=workflow_audit_sequence_retry``（DEBUG，高并发下避免刷屏）。
- 重试耗尽：``event=workflow_audit_sequence_exhausted``（ERROR）。
- PG 缺序列：``event=workflow_audit_pg_sequence_error``（ERROR，带 exc_info）。

禁止写入口令、令牌与 detail 全文（仅记录 detail 的键名）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger("app.workflow.audit")


def log_workflow_audit_appended(
    *,
    event_id: uuid.UUID,
    video_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    from_status: str,
    to_status: str,
    audit_sequence: int,
    detail: dict[str, Any] | None = None,
) -> None:
    """审计行已成功落库后调用（与 DB 提交解耦：由调用方在 flush/execute 成功后调用）。"""
    detail_keys = "-"
    if detail:
        detail_keys = ",".join(sorted(detail))
    logger.info(
        "event=workflow_audit "
        "event_id=%s video_id=%s actor_id=%s action=%s from_status=%s to_status=%s audit_sequence=%s detail_keys=%s",
        event_id,
        video_id,
        actor_id,
        action,
        from_status,
        to_status,
        audit_sequence,
        detail_keys,
    )


def log_workflow_audit_sequence_retry(
    *,
    video_id: uuid.UUID,
    action: str,
    attempt: int,
) -> None:
    """SQLite 等路径下 audit_sequence 撞唯一约束并重试（默认 DEBUG，避免高并发刷屏）。"""
    logger.debug(
        "event=workflow_audit_sequence_retry video_id=%s action=%s attempt=%s",
        video_id,
        action,
        attempt,
    )


def log_workflow_audit_sequence_exhausted(
    *,
    video_id: uuid.UUID,
    action: str,
    attempts: int,
) -> None:
    """重试耗尽：须人工关注（可能极高并发或数据异常）。"""
    logger.error(
        "event=workflow_audit_sequence_exhausted video_id=%s action=%s attempts=%s",
        video_id,
        action,
        attempts,
    )


def log_workflow_audit_pg_sequence_misconfigured(exc: BaseException) -> None:
    """PostgreSQL 上缺少 0014 序列或 DDL 不匹配时记录，便于运维定位。"""
    logger.error(
        "event=workflow_audit_pg_sequence_error hint=migration_0014_workflow_audit_sequence_pg_seq",
        exc_info=exc,
    )
