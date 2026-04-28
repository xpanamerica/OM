"""阿里云 VOD CreateUploadVideo OpenAPI 薄封装（供单测整体 patch）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VodCreateUploadResult:
    video_id: str
    upload_address: str
    upload_auth: str
    request_id: str


@dataclass(frozen=True)
class VodPlayAuthResult:
    """GetVideoPlayAuth 结果：供播放器 SDK 换短期可播地址，非永久直链。"""

    play_auth: str
    request_id: str


def call_create_upload_video(
    *,
    access_key_id: str,
    access_key_secret: str,
    region: str,
    title: str,
    file_name: str,
    description: str | None,
    cover_url: str | None,
    template_group_id: str | None,
    workflow_id: str | None,
) -> VodCreateUploadResult:
    """调用 VOD CreateUploadVideo；不向调用方暴露 AccessKey。"""
    try:
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models
        from alibabacloud_vod20170321.client import Client as VodClient
        from alibabacloud_vod20170321 import models as vod_models
    except ImportError as e:
        raise RuntimeError(
            "未安装阿里云 VOD SDK。请在 backend 目录执行: pip install -r requirements.txt "
            "（依赖包名: alibabacloud-vod20170321）"
        ) from e

    endpoint = f"vod.{region}.aliyuncs.com"
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=endpoint,
    )
    client = VodClient(config)
    req = vod_models.CreateUploadVideoRequest(title=title, file_name=file_name)
    _set_optional_str(req, description, "description", "Description")
    _set_optional_str(req, cover_url, "cover_url", "coverURL")
    _set_optional_str(req, template_group_id, "template_group_id", "templateGroupId")
    _set_optional_str(req, workflow_id, "workflow_id", "workflowId")

    runtime = util_models.RuntimeOptions()
    try:
        resp = client.create_upload_video_with_options(req, runtime)
    except Exception as e:
        # Tea 客户端错误信息供上层映射为 AppError
        raise RuntimeError(_format_vod_client_error(e)) from e

    body = resp.body
    if body is None:
        raise RuntimeError("阿里云 VOD 返回空响应体")

    vid = getattr(body, "video_id", None) or getattr(body, "videoId", None)
    uaddr = getattr(body, "upload_address", None) or getattr(body, "uploadAddress", None)
    uauth = getattr(body, "upload_auth", None) or getattr(body, "uploadAuth", None)
    rid = getattr(body, "request_id", None) or getattr(body, "requestId", None)

    if not all(isinstance(x, str) and x for x in (vid, uaddr, uauth, rid)):
        raise RuntimeError("阿里云 VOD 响应缺少 VideoId / UploadAddress / UploadAuth / RequestId")

    return VodCreateUploadResult(
        video_id=str(vid),
        upload_address=str(uaddr),
        upload_auth=str(uauth),
        request_id=str(rid),
    )


def call_refresh_upload_video(
    *,
    access_key_id: str,
    access_key_secret: str,
    region: str,
    vod_video_id: str,
) -> VodCreateUploadResult:
    """调用 VOD RefreshUploadVideo，用于上传凭证过期后换新 ``UploadAddress`` / ``UploadAuth``。"""
    try:
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models
        from alibabacloud_vod20170321.client import Client as VodClient
        from alibabacloud_vod20170321 import models as vod_models
    except ImportError as e:
        raise RuntimeError(
            "未安装阿里云 VOD SDK。请在 backend 目录执行: pip install -r requirements.txt "
            "（依赖包名: alibabacloud-vod20170321）"
        ) from e

    endpoint = f"vod.{region}.aliyuncs.com"
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=endpoint,
    )
    client = VodClient(config)
    req = vod_models.RefreshUploadVideoRequest(video_id=vod_video_id.strip())

    runtime = util_models.RuntimeOptions()
    try:
        resp = client.refresh_upload_video_with_options(req, runtime)
    except Exception as e:
        raise RuntimeError(_format_vod_client_error(e)) from e

    body = resp.body
    if body is None:
        raise RuntimeError("阿里云 VOD RefreshUploadVideo 返回空响应体")

    vid = getattr(body, "video_id", None) or getattr(body, "videoId", None)
    uaddr = getattr(body, "upload_address", None) or getattr(body, "uploadAddress", None)
    uauth = getattr(body, "upload_auth", None) or getattr(body, "uploadAuth", None)
    rid = getattr(body, "request_id", None) or getattr(body, "requestId", None)

    if not all(isinstance(x, str) and x for x in (vid, uaddr, uauth, rid)):
        raise RuntimeError("阿里云 VOD RefreshUploadVideo 响应缺少 VideoId / UploadAddress / UploadAuth / RequestId")

    return VodCreateUploadResult(
        video_id=str(vid),
        upload_address=str(uaddr),
        upload_auth=str(uauth),
        request_id=str(rid),
    )


def call_get_video_play_auth(
    *,
    access_key_id: str,
    access_key_secret: str,
    region: str,
    vod_video_id: str,
    auth_info_timeout_seconds: int | None,
) -> VodPlayAuthResult:
    """调用 VOD GetVideoPlayAuth：返回短时 PlayAuth，由阿里云播放器 SDK 再换取真实流地址。

    相对 GetPlayInfo 直接返回 URL：PlayAuth 与控制台「URL 鉴权 / 私有加密」配合更好，凭证过期即失效，
    避免把可长期扩散的固定播放链接当作唯一交付物。
    """
    try:
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models
        from alibabacloud_vod20170321.client import Client as VodClient
        from alibabacloud_vod20170321 import models as vod_models
    except ImportError as e:
        raise RuntimeError(
            "未安装阿里云 VOD SDK。请在 backend 目录执行: pip install -r requirements.txt "
            "（依赖包名: alibabacloud-vod20170321）"
        ) from e

    endpoint = f"vod.{region}.aliyuncs.com"
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=endpoint,
    )
    client = VodClient(config)
    req = vod_models.GetVideoPlayAuthRequest(video_id=vod_video_id)
    if auth_info_timeout_seconds is not None:
        _set_optional_int(req, auth_info_timeout_seconds, "auth_info_timeout", "authInfoTimeout")

    runtime = util_models.RuntimeOptions()
    try:
        resp = client.get_video_play_auth_with_options(req, runtime)
    except Exception as e:
        raise RuntimeError(_format_vod_client_error(e)) from e

    body = resp.body
    if body is None:
        raise RuntimeError("阿里云 VOD GetVideoPlayAuth 返回空响应体")

    auth = getattr(body, "play_auth", None) or getattr(body, "playAuth", None)
    rid = getattr(body, "request_id", None) or getattr(body, "requestId", None)
    if not isinstance(auth, str) or not auth:
        raise RuntimeError("阿里云 VOD 响应缺少 PlayAuth")
    if not isinstance(rid, str) or not rid:
        rid = ""

    return VodPlayAuthResult(play_auth=str(auth), request_id=str(rid))


def _set_optional_int(req: object, val: int, *attr_names: str) -> None:
    for n in attr_names:
        if hasattr(req, n):
            setattr(req, n, val)
            return


def _set_optional_str(req: object, val: str | None, *attr_names: str) -> None:
    if not val:
        return
    for n in attr_names:
        if hasattr(req, n):
            setattr(req, n, val)
            return


def _format_vod_client_error(exc: BaseException) -> str:
    parts: list[str] = [str(exc).strip() or type(exc).__name__]
    for attr in ("code", "data", "message", "statusCode", "status_code"):
        if hasattr(exc, attr):
            v = getattr(exc, attr)
            if v is not None and str(v).strip():
                parts.append(f"{attr}={v}")
    return "；".join(parts)[:2000]
