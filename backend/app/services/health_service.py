from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.attachment_upload_rate_limit import (
    attachment_post_rate_limit_operational,
    attachment_post_rate_limit_storage_label,
)
from app.core.comment_rate_limit import comment_rate_limit_operational, comment_rate_limit_storage_label
from app.core.vod_refresh_upload_rate_limit import (
    vod_refresh_rate_limit_operational,
    vod_refresh_rate_limit_storage_label,
)
from app.core.config import settings
from app.db.session import SessionLocal
from app.infrastructure.redis import ping_redis


def full_health_report() -> dict:
    """返回根路径与后续 admin 探针共用的健康 JSON（HTTP 始终 200，由字段区分降级）。"""
    database = "disconnected"
    try:
        db: Session = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            database = "connected"
        finally:
            db.close()
    except Exception:
        database = "disconnected"

    redis_ok = ping_redis()
    redis = "connected" if redis_ok else "disconnected"
    rl_ok = comment_rate_limit_operational(redis_connected=redis_ok)
    vod_rl_ok = vod_refresh_rate_limit_operational(redis_connected=redis_ok)
    att_rl_ok = attachment_post_rate_limit_operational(redis_connected=redis_ok)
    status = (
        "ok"
        if database == "connected" and redis_ok and rl_ok and vod_rl_ok and att_rl_ok
        else "degraded"
    )
    return {
        "status": status,
        "database": database,
        "redis": redis,
        "comment_rate_limit_storage": comment_rate_limit_storage_label(),
        "comment_rate_limit_use_redis": settings.COMMENT_RATE_LIMIT_USE_REDIS,
        "comment_rate_limit_redis_fallback_memory": settings.COMMENT_RATE_LIMIT_REDIS_FALLBACK_MEMORY,
        "comment_rate_limit_operational": rl_ok,
        "vod_refresh_rate_limit_storage": vod_refresh_rate_limit_storage_label(),
        "vod_refresh_rate_limit_use_redis": settings.VOD_REFRESH_UPLOAD_RATE_LIMIT_USE_REDIS,
        "vod_refresh_rate_limit_redis_fallback_memory": settings.VOD_REFRESH_UPLOAD_RATE_LIMIT_REDIS_FALLBACK_MEMORY,
        "vod_refresh_rate_limit_operational": vod_rl_ok,
        "attachment_post_rate_limit_storage": attachment_post_rate_limit_storage_label(),
        "attachment_post_rate_limit_use_redis": settings.ATTACHMENT_POST_RATE_LIMIT_USE_REDIS,
        "attachment_post_rate_limit_redis_fallback_memory": settings.ATTACHMENT_POST_RATE_LIMIT_REDIS_FALLBACK_MEMORY,
        "attachment_post_rate_limit_operational": att_rl_ok,
    }
