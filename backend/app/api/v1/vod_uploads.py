"""阶段 11.1：阿里云 VOD 上传凭证 HTTP 层；11.4：VOD 事件回调。"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies.auth import CurrentUser
from app.api.v1.http_cache_control import set_mutation_cache_control
from app.api.deps import DbSession
from app.core.exceptions import AppError
from app.core.vod_codes import VOD_CALLBACK_INVALID_JSON, VOD_CALLBACK_UNAUTHORIZED
from app.schemas.vod_callback import VodCallbackAck, VodCallbackIn
from app.schemas.vod_upload import VodCreateUploadRequest, VodCreateUploadResponse, VodRefreshUploadRequest
from app.services import vod_callback_service, vod_service

router = APIRouter()

VodCallbackSecretHeader = Annotated[
    str | None,
    Header(
        alias="X-VOD-Callback-Secret",
        description="须与服务器环境变量 ALIYUN_VOD_CALLBACK_SECRET 一致；勿泄露。",
    ),
]


@router.post(
    "/vod/create-upload-video",
    response_model=VodCreateUploadResponse,
    summary="获取阿里云 VOD 上传凭证",
    description=(
        "需登录。服务端使用配置的 RAM 凭证调用 **CreateUploadVideo**，返回 **UploadAddress** / **UploadAuth** / **VideoId**；"
        "**不会**返回 AccessKey。前端/SDK 凭返回字段向 OSS 直传媒资（本阶段不实现上传本身）。"
        "阶段 12：校验 ``file_size``、扩展名白名单、标题/描述长度；普通用户受每日上传次数限制（UTC）；"
        "成功发凭证后写入 ``upload_intents`` 审计表。"
    ),
    responses={
        400: {
            "description": (
                "扩展名、大小或标题/描述不符合安全策略；JSON ``code`` 如 "
                "`UPLOAD_VIDEO_EXTENSION_NOT_ALLOWED` / `UPLOAD_VIDEO_FILE_TOO_LARGE` / "
                "`UPLOAD_TITLE_TOO_LONG` / `UPLOAD_DESCRIPTION_TOO_LONG` / `UPLOAD_COVER_EXTENSION_NOT_ALLOWED`"
            )
        },
        401: {"description": "未登录"},
        429: {"description": "普通用户超过 VIDEO_UPLOAD_MAX_PER_USER_PER_DAY（`Retry-After` 为至 UTC 次日零点的秒数）"},
        502: {"description": "阿里云 VOD 调用失败"},
        503: {"description": "未配置 VOD、SDK 未安装，或严格 Redis 限流后端不可用"},
    },
    dependencies=[Depends(set_mutation_cache_control)],
)
def create_upload_video_vod(
    db: DbSession,
    current_user: CurrentUser,
    body: VodCreateUploadRequest,
) -> VodCreateUploadResponse:
    return vod_service.create_upload_video_credentials(db=db, actor=current_user, body=body)


@router.post(
    "/vod/refresh-upload-video",
    response_model=VodCreateUploadResponse,
    summary="刷新 VOD 上传地址与凭证",
    description=(
        "需登录。服务端调用 **RefreshUploadVideo**，返回新的 **UploadAddress** / **UploadAuth**（同一 VideoId）。"
        "普通用户仅当存在本人 ``upload_intents`` 中对应 ``vod_video_id`` 的记录时可刷新；**管理员**不受此限。"
        "不消耗每日 CreateUploadVideo 次数；不写入新的 ``upload_intents``。"
    ),
    responses={
        401: {"description": "未登录"},
        403: {"description": "无刷新权限（`VOD_REFRESH_UPLOAD_FORBIDDEN`）"},
        429: {"description": "刷新过于频繁（`VOD_REFRESH_UPLOAD_RATE_LIMITED`；管理员不受限）"},
        502: {"description": "阿里云 VOD 调用失败"},
        503: {
            "description": (
                "未配置 VOD 或 SDK 未安装；或已关闭 Redis 回退且限流后端不可用（`UPLOAD_RATE_LIMIT_BACKEND_UNAVAILABLE`）"
            )
        },
    },
    dependencies=[Depends(set_mutation_cache_control)],
)
def refresh_upload_video_vod(
    db: DbSession,
    current_user: CurrentUser,
    body: VodRefreshUploadRequest,
) -> VodCreateUploadResponse:
    return vod_service.refresh_upload_video_credentials(db=db, actor=current_user, body=body)


@router.post(
    "/vod/callback",
    response_model=VodCallbackAck,
    summary="阿里云 VOD HTTP 回调",
    description=(
        "**无需用户登录**；必须携带 ``X-VOD-Callback-Secret``（与 ``ALIYUN_VOD_CALLBACK_SECRET`` 一致）。"
        "根据 ``EventType`` 更新本地 ``upload_status`` / ``transcode_status`` / ``duration_seconds``，"
        "**不**修改审核状态（``draft`` / ``published`` 等）。"
        "未识别事件仍返回 200（`event_kind=unknown`）。**上传/转码等已识别事件**：缺少 ``VideoId`` 返回 **400**；"
        "``VideoId`` 在本地无绑定返回 **404**（便于排障；阿里云可能对非 2xx 重试，请在控制台与绑定数据侧对齐）。"
    ),
    responses={
        400: {"description": "Body 非合法 JSON，或已识别事件缺少 VideoId（`VOD_CALLBACK_INVALID_JSON` / `VOD_CALLBACK_VIDEO_ID_MISSING`）"},
        401: {
            "description": (
                "鉴权失败：``X-VOD-Callback-Secret`` 缺失、仅空白或与配置不一致；"
                "或已启用扩展签名校验时 Body 签名校验未通过（`VOD_CALLBACK_UNAUTHORIZED`）"
            )
        },
        404: {"description": "本地无稿件绑定该 VideoId（`VOD_CALLBACK_VIDEO_NOT_FOUND`）"},
        503: {"description": "未配置 ALIYUN_VOD_CALLBACK_SECRET"},
        200: {"description": "已处理（仅未知事件或未产生写库变更时 `updated` 可能为 false）"},
    },
    dependencies=[Depends(set_mutation_cache_control)],
)
async def vod_http_callback(
    request: Request,
    db: DbSession,
    x_vod_callback_secret: VodCallbackSecretHeader = None,
) -> VodCallbackAck:
    raw = await request.body()
    vod_callback_service.verify_vod_callback_secret(x_vod_callback_secret)
    hdr_map = {k: v for k, v in request.headers.items()}
    if not vod_callback_service.vod_callback_body_signature_ok(raw, hdr_map):
        raise AppError("VOD 回调签名校验未通过", status_code=401, code=VOD_CALLBACK_UNAUTHORIZED)

    try:
        data = json.loads(raw.decode("utf-8") if raw else b"{}")
    except json.JSONDecodeError as e:
        raise AppError("VOD 回调 Body 须为合法 JSON", status_code=400, code=VOD_CALLBACK_INVALID_JSON) from e
    payload = VodCallbackIn.model_validate(data)
    return vod_callback_service.apply_vod_callback(db, payload)
