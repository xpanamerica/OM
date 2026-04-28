"""阶段 11.4：阿里云 VOD HTTP 回调 → 同步 upload/transcode 状态（不改审核状态）。"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.core import config
from app.core.exceptions import AppError
from app.core.vod_codes import (
    VOD_CALLBACK_NOT_CONFIGURED,
    VOD_CALLBACK_UNAUTHORIZED,
    VOD_CALLBACK_VIDEO_ID_MISSING,
    VOD_CALLBACK_VIDEO_NOT_FOUND,
)
from app.models.enums import VodTranscodeStatus, VodUploadStatus
from app.models.video import Video
from app.repositories import video_repository
from app.schemas.vod_callback import VodCallbackAck, VodCallbackIn

logger = logging.getLogger(__name__)


class _NormalizedEvent(str, Enum):
    UPLOAD_COMPLETE = "upload_complete"
    TRANSCODE_COMPLETE = "transcode_complete"
    TRANSCODE_FAILED = "transcode_failed"
    UNKNOWN = "unknown"


def verify_vod_callback_secret(header_value: str | None) -> None:
    """MVP：校验 ``X-VOD-Callback-Secret`` 与环境变量 ``ALIYUN_VOD_CALLBACK_SECRET`` 一致（恒定时间比较）。"""
    cfg = config.settings.ALIYUN_VOD_CALLBACK_SECRET
    if cfg is None:
        raise AppError(
            "未配置 VOD 回调密钥：请设置环境变量 ALIYUN_VOD_CALLBACK_SECRET",
            status_code=503,
            code=VOD_CALLBACK_NOT_CONFIGURED,
        )
    expected = cfg.get_secret_value()
    if not expected:
        raise AppError(
            "VOD 回调密钥为空",
            status_code=503,
            code=VOD_CALLBACK_NOT_CONFIGURED,
        )
    got = (header_value or "").strip()
    try:
        ok = secrets.compare_digest(got.encode("utf-8"), expected.encode("utf-8"))
    except (TypeError, ValueError):
        ok = False
    if not ok:
        raise AppError("VOD 回调鉴权失败", status_code=401, code=VOD_CALLBACK_UNAUTHORIZED)


def vod_callback_body_signature_ok(_body: bytes, headers: dict[str, str]) -> bool:
    """占位：后续可校验 ``X-VOD-Signature`` / HMAC-SHA256(body) 等，与控制台签名配置对齐。

    MVP 仅依赖 ``verify_vod_callback_secret``；返回 True 表示未启用签名扩展。
    """
    _ = _body, headers
    return True


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _classify_event(payload: VodCallbackIn) -> _NormalizedEvent:
    et = _norm(payload.event_type)
    if et == "FileUploadComplete":
        return _NormalizedEvent.UPLOAD_COMPLETE
    if et == "TranscodeComplete":
        st = _norm(payload.status).lower()
        if st == "fail":
            return _NormalizedEvent.TRANSCODE_FAILED
        streams = payload.stream_infos or []
        if streams and all(_norm(x.get("Status")).lower() == "fail" for x in streams):
            return _NormalizedEvent.TRANSCODE_FAILED
        return _NormalizedEvent.TRANSCODE_COMPLETE
    # 可扩展：不同地域/工作流事件名
    if et in ("StreamTranscodeComplete", "AllTranscodeComplete"):
        return _NormalizedEvent.TRANSCODE_COMPLETE
    if et in ("TranscodeFail", "TranscodeFailed"):
        return _NormalizedEvent.TRANSCODE_FAILED
    return _NormalizedEvent.UNKNOWN


def _max_duration_seconds(streams: list[dict[str, Any]]) -> int | None:
    best: int | None = None
    for s in streams:
        if _norm(s.get("Status")).lower() != "success":
            continue
        d = s.get("Duration")
        if isinstance(d, bool):
            continue
        if isinstance(d, (int, float)):
            sec = int(d)
            if best is None or sec > best:
                best = sec
    return best


_HANDLED_REQUIRES_BOUND_VIDEO: frozenset[_NormalizedEvent] = frozenset(
    (
        _NormalizedEvent.UPLOAD_COMPLETE,
        _NormalizedEvent.TRANSCODE_COMPLETE,
        _NormalizedEvent.TRANSCODE_FAILED,
    )
)


def apply_vod_callback(db: Session, payload: VodCallbackIn) -> VodCallbackAck:
    """根据回调更新 ``videos`` 的 VOD 侧字段；**不**修改 ``VideoStatus``（审核/上下架）。"""
    kind = _classify_event(payload)
    vod_vid = _norm(payload.video_id)

    if kind == _NormalizedEvent.UNKNOWN:
        logger.info("vod callback unhandled EventType=%s VideoId=%s", payload.event_type, vod_vid or "")
        return VodCallbackAck(
            accepted=True,
            updated=False,
            video_id=None,
            vod_video_id=vod_vid or None,
            event_kind=kind.value,
        )

    if kind in _HANDLED_REQUIRES_BOUND_VIDEO:
        if not vod_vid:
            logger.warning("vod callback missing VideoId for handled event=%s", kind.value)
            raise AppError(
                "回调缺少 VideoId，无法匹配本地已绑定稿件",
                status_code=400,
                code=VOD_CALLBACK_VIDEO_ID_MISSING,
            )
        row = video_repository.get_by_vod_video_id(db, vod_vid)
        if row is None:
            logger.warning("vod callback no local row for VideoId=%s event=%s", vod_vid, kind.value)
            raise AppError(
                "本地不存在绑定该 VOD VideoId 的稿件",
                status_code=404,
                code=VOD_CALLBACK_VIDEO_NOT_FOUND,
            )

    changed = _apply_event_to_row(row, payload, kind)
    if changed:
        row.updated_at = datetime.now(timezone.utc)
        db.commit()

    return VodCallbackAck(
        accepted=True,
        updated=changed,
        video_id=str(row.id),
        vod_video_id=vod_vid,
        event_kind=kind.value,
    )


def _apply_event_to_row(row: Video, payload: VodCallbackIn, kind: _NormalizedEvent) -> bool:
    changed = False
    if kind == _NormalizedEvent.UPLOAD_COMPLETE:
        st = _norm(payload.status).lower()
        if st == "success":
            if row.upload_status != VodUploadStatus.UPLOADED:
                row.upload_status = VodUploadStatus.UPLOADED
                changed = True
            if row.transcode_status == VodTranscodeStatus.NONE:
                row.transcode_status = VodTranscodeStatus.PENDING
                changed = True
        elif st == "fail":
            if row.upload_status != VodUploadStatus.FAILED:
                row.upload_status = VodUploadStatus.FAILED
                changed = True
        else:
            if row.upload_status != VodUploadStatus.UPLOADED:
                row.upload_status = VodUploadStatus.UPLOADED
                changed = True
    elif kind == _NormalizedEvent.TRANSCODE_COMPLETE:
        if row.transcode_status != VodTranscodeStatus.COMPLETED:
            row.transcode_status = VodTranscodeStatus.COMPLETED
            changed = True
        streams = payload.stream_infos or []
        dur = _max_duration_seconds(streams)
        if dur is not None and row.duration_seconds != dur:
            row.duration_seconds = dur
            changed = True
    elif kind == _NormalizedEvent.TRANSCODE_FAILED:
        if row.transcode_status != VodTranscodeStatus.FAILED:
            row.transcode_status = VodTranscodeStatus.FAILED
            changed = True

    return changed
