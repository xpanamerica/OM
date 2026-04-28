"""评论域可观测日志（不写 ``content`` 正文，仅长度与 id）。"""

from __future__ import annotations

import logging
import uuid

from app.core.request_context import request_id_cv

logger = logging.getLogger("app.comment.audit")


def log_comment_created(
    *,
    comment_id: uuid.UUID,
    video_id: uuid.UUID,
    user_id: uuid.UUID,
    content_len: int,
) -> None:
    rid = request_id_cv.get()
    logger.info(
        "event=comment_created request_id=%s comment_id=%s video_id=%s user_id=%s content_len=%s",
        rid or "-",
        comment_id,
        video_id,
        user_id,
        content_len,
    )


def log_comment_soft_deleted(
    *,
    comment_id: uuid.UUID,
    video_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    rid = request_id_cv.get()
    logger.info(
        "event=comment_soft_deleted request_id=%s comment_id=%s video_id=%s actor_id=%s",
        rid or "-",
        comment_id,
        video_id,
        actor_id,
    )
