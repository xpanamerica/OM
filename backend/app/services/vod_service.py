"""阶段 11.1：阿里云 VOD 上传凭证；阶段 11.3：播放凭证 GetVideoPlayAuth；阶段 12：上传安全与意图落库。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core import upload_rate_limit, upload_security, vod_refresh_upload_rate_limit
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.vod_codes import (
    VOD_API_ERROR,
    VOD_CONFIG_INCOMPLETE,
    VOD_REFRESH_UPLOAD_FORBIDDEN,
    VOD_SDK_NOT_INSTALLED,
)
from app.infrastructure.observability.upload_flow_metrics import (
    inc_vod_refresh_upload_aliyun_error,
    inc_vod_refresh_upload_success,
)
from app.infrastructure.aliyun_vod_api import (
    VodCreateUploadResult,
    VodPlayAuthResult,
    call_create_upload_video,
    call_get_video_play_auth,
    call_refresh_upload_video,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import upload_intent_repository
from app.schemas.vod_play import VideoPlayResponse
from app.schemas.vod_upload import VodCreateUploadRequest, VodCreateUploadResponse, VodRefreshUploadRequest

logger = logging.getLogger(__name__)


def create_upload_video_credentials(
    *, db: Session, actor: User, body: VodCreateUploadRequest
) -> VodCreateUploadResponse:
    """为已登录用户向阿里云 VOD 申请 CreateUploadVideo 凭证；成功则写入 ``upload_intents``。"""
    upload_security.assert_vod_upload_payload_ok(
        title=body.title,
        description=body.description,
        filename=body.filename,
        file_size=body.file_size,
        cover_url=body.cover_url,
    )

    reserved_slot = False
    if actor.role == UserRole.USER:
        upload_rate_limit.begin_vod_upload_daily_attempt(actor.id)
        reserved_slot = True

    try:
        ak = (settings.ALIYUN_ACCESS_KEY_ID or "").strip()
        sk = settings.ALIYUN_ACCESS_KEY_SECRET
        region = (settings.ALIYUN_VOD_REGION or "").strip()
        if not ak or sk is None or not region:
            raise AppError(
                "阿里云 VOD 未配置：请在环境变量中设置 ALIYUN_ACCESS_KEY_ID、ALIYUN_ACCESS_KEY_SECRET、ALIYUN_VOD_REGION",
                status_code=503,
                code=VOD_CONFIG_INCOMPLETE,
            )
        secret = sk.get_secret_value().strip()
        if not secret:
            raise AppError(
                "阿里云 VOD 未配置：ALIYUN_ACCESS_KEY_SECRET 为空",
                status_code=503,
                code=VOD_CONFIG_INCOMPLETE,
            )

        try:
            result: VodCreateUploadResult = call_create_upload_video(
                access_key_id=ak,
                access_key_secret=secret,
                region=region,
                title=body.title,
                file_name=body.filename,
                description=body.description,
                cover_url=body.cover_url,
                template_group_id=settings.ALIYUN_VOD_TEMPLATE_GROUP_ID,
                workflow_id=settings.ALIYUN_VOD_WORKFLOW_ID,
            )
        except RuntimeError as e:
            msg = str(e)
            if "未安装阿里云 VOD SDK" in msg or "alibabacloud" in msg.lower():
                raise AppError(msg, status_code=503, code=VOD_SDK_NOT_INSTALLED) from None
            logger.warning("vod_create_upload_video failed: %s", msg)
            raise AppError(f"阿里云 VOD 调用失败：{msg}", status_code=502, code=VOD_API_ERROR) from None
    except AppError:
        if reserved_slot:
            upload_rate_limit.abort_vod_upload_daily_attempt(actor.id)
        raise

    upload_intent_repository.create_intent(
        db,
        user_id=actor.id,
        filename=body.filename,
        file_size=body.file_size,
        vod_video_id=result.video_id,
    )
    db.commit()

    return VodCreateUploadResponse(
        video_id_from_vod=result.video_id,
        upload_address=result.upload_address,
        upload_auth=result.upload_auth,
        request_id=result.request_id,
    )


def refresh_upload_video_credentials(
    *, db: Session, actor: User, body: VodRefreshUploadRequest
) -> VodCreateUploadResponse:
    """为已登录用户调用 **RefreshUploadVideo**；普通用户须存在本人 ``upload_intents`` 记录（与 VideoId 对应）。"""
    vod_id = body.vod_video_id.strip()
    if actor.role != UserRole.ADMIN and not upload_intent_repository.exists_intent_for_user_and_vod_video_id(
        db, user_id=actor.id, vod_video_id=vod_id
    ):
        raise AppError(
            "仅可为本人近期通过本系统申请过上传凭证的 VideoId 刷新上传地址；若需运维改绑请联系管理员",
            status_code=403,
            code=VOD_REFRESH_UPLOAD_FORBIDDEN,
        )

    if actor.role != UserRole.ADMIN:
        vod_refresh_upload_rate_limit.consume_vod_refresh_upload_slot_or_raise(user_id=actor.id)

    ak = (settings.ALIYUN_ACCESS_KEY_ID or "").strip()
    sk = settings.ALIYUN_ACCESS_KEY_SECRET
    region = (settings.ALIYUN_VOD_REGION or "").strip()
    if not ak or sk is None or not region:
        raise AppError(
            "阿里云 VOD 未配置：请在环境变量中设置 ALIYUN_ACCESS_KEY_ID、ALIYUN_ACCESS_KEY_SECRET、ALIYUN_VOD_REGION",
            status_code=503,
            code=VOD_CONFIG_INCOMPLETE,
        )
    secret = sk.get_secret_value().strip()
    if not secret:
        raise AppError(
            "阿里云 VOD 未配置：ALIYUN_ACCESS_KEY_SECRET 为空",
            status_code=503,
            code=VOD_CONFIG_INCOMPLETE,
        )

    try:
        result: VodCreateUploadResult = call_refresh_upload_video(
            access_key_id=ak,
            access_key_secret=secret,
            region=region,
            vod_video_id=vod_id,
        )
    except RuntimeError as e:
        msg = str(e)
        if "未安装阿里云 VOD SDK" in msg or "alibabacloud" in msg.lower():
            raise AppError(msg, status_code=503, code=VOD_SDK_NOT_INSTALLED) from None
        logger.warning("vod_refresh_upload_video failed: %s", msg)
        inc_vod_refresh_upload_aliyun_error()
        raise AppError(f"阿里云 VOD 刷新上传凭证失败：{msg}", status_code=502, code=VOD_API_ERROR) from None

    logger.info(
        "vod_refresh_upload_ok user_id=%s vod_video_id=%s request_id=%s",
        actor.id,
        vod_id,
        result.request_id,
    )
    inc_vod_refresh_upload_success()
    return VodCreateUploadResponse(
        video_id_from_vod=result.video_id,
        upload_address=result.upload_address,
        upload_auth=result.upload_auth,
        request_id=result.request_id,
    )


def get_video_play_auth_for_local_video(
    *,
    actor: User,
    video_local_id: uuid.UUID,
    vod_video_id: str,
) -> VideoPlayResponse:
    """向阿里云申请 **GetVideoPlayAuth**，返回短时 ``play_auth``（非永久播放 URL）。"""
    _ = actor

    ak = (settings.ALIYUN_ACCESS_KEY_ID or "").strip()
    sk = settings.ALIYUN_ACCESS_KEY_SECRET
    region = (settings.ALIYUN_VOD_REGION or "").strip()
    if not ak or sk is None or not region:
        raise AppError(
            "阿里云 VOD 未配置：请在环境变量中设置 ALIYUN_ACCESS_KEY_ID、ALIYUN_ACCESS_KEY_SECRET、ALIYUN_VOD_REGION",
            status_code=503,
            code=VOD_CONFIG_INCOMPLETE,
        )
    secret = sk.get_secret_value().strip()
    if not secret:
        raise AppError(
            "阿里云 VOD 未配置：ALIYUN_ACCESS_KEY_SECRET 为空",
            status_code=503,
            code=VOD_CONFIG_INCOMPLETE,
        )

    timeout = settings.ALIYUN_VOD_PLAY_AUTH_TIMEOUT_SECONDS
    try:
        result: VodPlayAuthResult = call_get_video_play_auth(
            access_key_id=ak,
            access_key_secret=secret,
            region=region,
            vod_video_id=vod_video_id.strip(),
            auth_info_timeout_seconds=timeout,
        )
    except RuntimeError as e:
        msg = str(e)
        if "未安装阿里云 VOD SDK" in msg or "alibabacloud" in msg.lower():
            raise AppError(msg, status_code=503, code=VOD_SDK_NOT_INSTALLED) from None
        logger.warning("vod_get_video_play_auth failed: %s", msg)
        raise AppError(f"阿里云 VOD 获取播放凭证失败：{msg}", status_code=502, code=VOD_API_ERROR) from None

    expire: datetime | None = None
    if timeout is not None:
        expire = datetime.now(timezone.utc) + timedelta(seconds=int(timeout))

    return VideoPlayResponse(
        video_id=video_local_id,
        playback_mode="vod",
        vod_video_id=vod_video_id.strip(),
        play_auth=result.play_auth,
        stream_url=None,
        expire_time=expire,
        request_id=result.request_id or None,
    )
