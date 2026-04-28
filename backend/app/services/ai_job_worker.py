"""阶段 15：Mock AI 执行器（占位；后续可换为真实模型 / 队列消费者）。"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.models.enums import AiJobStatus
from app.repositories import ai_job_repository

logger = logging.getLogger(__name__)


def transition_pending_to_processing(db: Session, job_id: uuid.UUID) -> bool:
    """若任务仍为 ``pending``，则置为 ``processing`` 并 ``commit``。返回是否发生转换。"""
    row = ai_job_repository.get_by_id(db, job_id)
    if row is None:
        return False
    if row.status != AiJobStatus.PENDING:
        return False
    row.status = AiJobStatus.PROCESSING
    db.commit()
    return True


def transition_processing_to_completed_mock(db: Session, job_id: uuid.UUID) -> bool:
    """若任务为 ``processing``，则写入 Mock ``output_payload`` 并 ``completed``；否则不修改。"""
    row = ai_job_repository.get_by_id(db, job_id)
    if row is None:
        return False
    if row.status != AiJobStatus.PROCESSING:
        return False
    row.status = AiJobStatus.COMPLETED
    row.output_payload = {
        "provider": "mock",
        "job_type": row.job_type.value,
        "stub": True,
        "message": "阶段 15 占位结果：未调用真实大模型",
    }
    row.error_message = None
    db.commit()
    return True


def execute_mock_ai_job(job_id: uuid.UUID) -> None:
    """在独立 DB 会话中运行，供 ``BackgroundTasks`` 调用。"""
    from app.db.session import SessionLocal

    db: Session = SessionLocal()
    try:
        _run_mock_in_session(db, job_id)
    except Exception:
        logger.exception("mock ai job failed job_id=%s", job_id)
        try:
            row = ai_job_repository.get_by_id(db, job_id)
            if row is not None:
                row.status = AiJobStatus.FAILED
                row.error_message = "Mock 执行器异常（详见服务端日志）"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _run_mock_in_session(db: Session, job_id: uuid.UUID) -> None:
    if not transition_pending_to_processing(db, job_id):
        return
    time.sleep(0.002)
    transition_processing_to_completed_mock(db, job_id)
