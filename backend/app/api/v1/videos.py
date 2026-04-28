from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from starlette.responses import FileResponse

from app.api.deps import DbSession
from app.api.v1.http_cache_control import (
    MUTABLE_GET_CACHE_CONTROL,
    MUTATION_RESPONSE_CACHE_CONTROL,
    set_mutation_cache_control,
)
from app.api.v1.video_http import if_none_match_matches, weak_etag_for_video
from app.api.v1.video_idempotency import (
    IdempotencyKeyHeader,
    run_idempotent_video_bind_vod,
    run_idempotent_video_create,
    run_idempotent_video_patch,
)
from app.api.v1.video_openapi import (
    VIDEO_BIND_VOD_PATCH_RESPONSES,
    VIDEO_DETAIL_GET_RESPONSES,
    VIDEO_LIST_GET_RESPONSES,
    VIDEO_PATCH_RESPONSES,
    VIDEO_PLAY_GET_RESPONSES,
    VIDEO_POST_RESPONSES,
)
from app.api.v1.video_query import VideoListCursor, VideoListLimit, VideoListOffset
from app.api.dependencies.auth import AdminUser, CurrentUser, OptionalUser
from app.core.exceptions import AppError
from app.core.video_codes import (
    VIDEO_LIST_FOLLOW_FEED_REQUIRES_AUTH,
    VIDEO_NOT_FOUND,
    VIDEO_PLAY_NO_MEDIA,
)
from app.core.video_cursor import encode_video_list_cursor
from app.models.enums import VideoStatus
from app.repositories import video_repository
from app.schemas.video import VideoBindVodRequest, VideoCreate, VideoFeedResponse, VideoListItem, VideoResponse, VideoUpdate
from app.schemas.vod_play import VideoPlayResponse
from app.services import local_video_media_service, video_cover_service, video_privacy, video_service, vod_service

router = APIRouter()


@router.post(
    "",
    response_model=VideoResponse,
    status_code=201,
    summary="创建视频",
    description=(
        "需登录；新视频默认 `draft`。`category_id` 可选；`tag_ids` 须为已存在标签。"
        "可带 `Idempotency-Key` 防止重复创建。"
    ),
    responses=VIDEO_POST_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def create_video(
    db: DbSession,
    current_user: CurrentUser,
    body: VideoCreate,
    idempotency_key: IdempotencyKeyHeader = None,
) -> VideoResponse:
    return run_idempotent_video_create(
        actor_id=str(current_user.id),
        body=body,
        idempotency_key=idempotency_key,
        execute=lambda: video_service.create_video(db, current_user, body),
    )


@router.get(
    "",
    response_model=list[VideoListItem],
    summary="视频列表",
    description=(
        "非管理员仅能看到 `published`；`status` 查询参数仅管理员可用，"
        "非管理员传入将返回 400。响应头 `X-Total-Count` 为符合条件的总数；"
        "支持 `offset`+`limit` 或 `cursor`+`limit` 键集续页（与 taxonomy 规则一致）。"
        "含 `Cache-Control`、`Vary: Authorization`。"
        "**VOD 绑定细节**：`vod_video_id`、`source_file_name` 仅 **作者或管理员** 可见，其它身份为 `null`。"
    ),
    responses=VIDEO_LIST_GET_RESPONSES,
)
def list_videos(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    offset: VideoListOffset = 0,
    limit: VideoListLimit = 20,
    cursor: VideoListCursor = None,
    category_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    status: VideoStatus | None = None,
    author_id: uuid.UUID | None = None,
    followed_only: bool = Query(
        False,
        description="为 true 时仅返回当前用户所关注作者的已发布视频；必须携带有效 Bearer。",
    ),
):
    if followed_only and optional_user is None:
        raise AppError(
            "关注流需登录",
            status_code=401,
            code=VIDEO_LIST_FOLLOW_FEED_REQUIRES_AUTH,
        )
    follower_id = optional_user.id if followed_only else None
    items, total, has_more = video_service.list_videos(
        db,
        optional_user,
        offset=offset,
        limit=limit,
        cursor=cursor,
        category_id=category_id,
        tag_id=tag_id,
        status=status,
        author_id=author_id,
        follower_id_for_following=follower_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    response.headers["X-Has-More"] = "true" if has_more else "false"
    if has_more and items:
        last = items[-1]
        response.headers["X-Next-Cursor"] = encode_video_list_cursor(
            created_at=last.created_at, row_id=last.id
        )
    return [video_privacy.video_list_item_for_viewer(x, optional_user, db) for x in items]


@router.get(
    "/feed",
    response_model=VideoFeedResponse,
    summary="Feed 推荐列表",
    description=(
        "Feed 推荐接口。用户处于一键归源 origin mode 时，返回随机、多元、非画像化排序，"
        "并在响应体中包含 algorithmMode / personalized / explanation。"
    ),
)
def list_feed_videos(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    offset: VideoListOffset = 0,
    limit: VideoListLimit = 20,
    page: int = Query(1, ge=1, le=100_000, description="用于 origin mode 随机性的页码；与 explorationSeed 共同生成稳定随机序。"),
) -> VideoFeedResponse:
    items, total, has_more, algorithm_mode, personalized, explanation = video_service.list_feed_videos(
        db,
        optional_user,
        offset=offset,
        limit=limit,
        page=page,
    )
    video_service.record_feed_attention(db, viewer=optional_user, mode=algorithm_mode, items=items)
    item_out = []
    for x in items:
        row = video_privacy.video_list_item_for_viewer(x, optional_user, db)
        reason, text = video_service.recommendation_reason(mode=algorithm_mode, video=x)
        item_out.append(row.model_copy(update={"recommendation_reason": reason, "recommendation_text": text}))
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    response.headers["X-Has-More"] = "true" if has_more else "false"
    return VideoFeedResponse(
        items=item_out,
        total=total,
        hasMore=has_more,
        nextCursor=None,
        algorithmMode=algorithm_mode,
        personalized=personalized,
        explanation=explanation,
    )


@router.get(
    "/latest",
    response_model=list[VideoListItem],
    summary="最新视频",
    description="仅 **已发布**；按 ``created_at`` 倒序。``offset``+``limit`` 分页；``X-Total-Count`` 为已发布总数。",
    responses=VIDEO_LIST_GET_RESPONSES,
)
def list_latest_videos(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    offset: VideoListOffset = 0,
    limit: VideoListLimit = 20,
):
    items, total = video_service.list_latest_videos(db, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    response.headers["X-Has-More"] = "false"
    return [video_privacy.video_list_item_for_viewer(x, optional_user, db) for x in items]


@router.get(
    "/trending",
    response_model=list[VideoListItem],
    summary="热门视频",
    description=(
        "仅 **已发布**；线性热度分 "
        "``views_count×VIDEO_TRENDING_WEIGHT_VIEWS + likes_count×VIDEO_TRENDING_WEIGHT_LIKES + "
        "favorites_count×VIDEO_TRENDING_WEIGHT_FAVORITES`` 再乘时间衰减 "
        "（``VIDEO_TRENDING_RECENCY_HALF_LIFE_DAYS``>0 时启用，见配置说明）倒序（同分按 id；默认权重 1 / 4 / 6）。"
        "``offset``+``limit`` 分页；``X-Total-Count`` 为已发布总数。"
    ),
    responses=VIDEO_LIST_GET_RESPONSES,
)
def list_trending_videos(
    response: Response,
    db: DbSession,
    optional_user: OptionalUser,
    offset: VideoListOffset = 0,
    limit: VideoListLimit = 20,
):
    items, total = video_service.list_trending_videos(db, offset=offset, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    response.headers["X-Has-More"] = "false"
    return [video_privacy.video_list_item_for_viewer(x, optional_user, db) for x in items]


@router.get(
    "/{video_id}/play",
    response_model=VideoPlayResponse,
    summary="获取播放交付（本机优先或 VOD PlayAuth）",
    description=(
        "**需登录**。\n"
        "- **已发布**（`published`）：任意登录用户可获取播放信息。\n"
        "- **未发布**（`draft` / `pending_review` / `rejected`）：仅 **作者或管理员**。\n"
        "- **已下线**（`offline`）：**普通用户**不可；**作者或管理员**仍可获取（便于核对媒资）。\n"
        "- 若稿件已上传 **本机成片**（`local_video_relpath`），优先返回 ``playback_mode=local`` 与带短时 token 的 ``stream_url``（HTML5 ``<video>``，支持 Range）。\n"
        "- 否则若已绑定 ``vod_video_id``，返回 ``playback_mode=vod`` 与 **GetVideoPlayAuth** 的 ``play_auth``。\n"
        "- 二者皆无时返回 **400**（``VIDEO_PLAY_NO_MEDIA``）。\n\n"
        "**VOD 安全策略**：PlayAuth 短时有效，由阿里云播放器 SDK 换真实流；凭证失效后请重新请求本接口。"
    ),
    responses=VIDEO_PLAY_GET_RESPONSES,
)
def get_video_play(
    request: Request,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
) -> VideoPlayResponse:
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not video_service.can_view_video(v, current_user):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    video_service.assert_vod_play_permission(v, current_user)
    local_rel = (v.local_video_relpath or "").strip()
    if local_rel:
        response.headers["Cache-Control"] = MUTATION_RESPONSE_CACHE_CONTROL
        response.headers["Vary"] = "Authorization"
        return local_video_media_service.build_local_play_response(video=v, viewer=current_user, request=request)
    vod_id = (v.vod_video_id or "").strip()
    if not vod_id:
        raise AppError(
            "稿件未绑定点播且未上传本机成片，暂不可播放",
            status_code=400,
            code=VIDEO_PLAY_NO_MEDIA,
        )
    response.headers["Cache-Control"] = MUTATION_RESPONSE_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    return vod_service.get_video_play_auth_for_local_video(
        actor=current_user,
        video_local_id=v.id,
        vod_video_id=vod_id,
    )


@router.get(
    "/{video_id}/local-stream",
    name="video_local_stream",
    summary="本机成片流式输出（query token）",
    description="由 ``GET …/play`` 返回的 ``stream_url`` 引用；**勿**手写 token。支持 HTTP Range。",
    response_class=FileResponse,
)
def stream_local_video_file(
    db: DbSession,
    video_id: uuid.UUID,
    token: str,
) -> FileResponse:
    path, media_type = local_video_media_service.resolve_stream_file_path(
        db, token=token, path_video_id=video_id
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post(
    "/{video_id}/local-media",
    response_model=VideoResponse,
    summary="上传本机成片",
    description=(
        "将视频文件写入服务器 ``LOCAL_VIDEO_STORAGE_DIR``，并写入 ``local_video_relpath``。"
        "**仅作者或管理员**；扩展名须符合 ``ALLOWED_VIDEO_EXTENSIONS``；大小受 ``MAX_VIDEO_SIZE_MB`` 限制。"
        "成功后 **播放接口优先走本机**（无需阿里云配置）。"
        "大文件更推荐使用 ``PUT …/local-media-binary``（原始 body），本 multipart 路径会多一次服务端临时文件整拷贝。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_local_video_media(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    file: UploadFile = File(..., description="成片文件（如 mp4 / webm）"),
) -> VideoResponse:
    v = await local_video_media_service.save_upload_replace_local_file(
        db, actor=current_user, video_id=video_id, upload=file
    )
    return video_privacy.video_response_for_viewer(v, current_user)


@router.put(
    "/{video_id}/local-media-binary",
    response_model=VideoResponse,
    summary="上传本机成片（二进制直传，推荐）",
    description=(
        "请求体为 **原始文件字节**（非 ``multipart/form-data``），通常配合 "
        "``Content-Type: application/octet-stream`` 或 ``video/mp4``。"
        "相对 ``POST …/local-media`` 的 multipart，本接口 **少一次整文件临时落盘拷贝**，"
        "在本地服务器 / 反代后上传大文件时往往明显更快。"
        "须 query ``suffix``（如 ``.mp4``）；权限与大小限制同 multipart 接口。"
    ),
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_local_video_binary(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    request: Request,
    suffix: str = Query(
        ...,
        description="扩展名，须带点，如 .mp4；须落在 ``ALLOWED_VIDEO_EXTENSIONS`` 内",
    ),
    source_name: str | None = Query(
        None,
        description="可选；写入 ``source_file_name`` 供后台展示（默认用目标文件名）",
    ),
) -> VideoResponse:
    ct = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ct or ct.startswith("multipart/"):
        raise AppError(
            "本接口不接受 multipart；大文件请用原始 body，或使用 POST …/local-media。",
            status_code=415,
        )
    v = await local_video_media_service.save_raw_body_replace_local_file(
        db,
        actor=current_user,
        video_id=video_id,
        request=request,
        suffix=suffix,
        source_file_name=source_name,
    )
    return video_privacy.video_response_for_viewer(v, current_user)


@router.post(
    "/{video_id}/cover",
    response_model=VideoResponse,
    summary="上传稿件封面（JPEG）",
    description="**仅作者或管理员**；写入 ``VIDEO_COVER_STORAGE_DIR`` 并设置 ``cover_url`` 为公开 ``GET /covers/{id}.jpg`` 路径。",
    dependencies=[Depends(set_mutation_cache_control)],
)
async def upload_video_cover_image(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    file: UploadFile = File(..., description="JPEG 封面图"),
) -> VideoResponse:
    v = await video_cover_service.save_cover_upload(db, actor=current_user, video_id=video_id, upload=file)
    return video_privacy.video_response_for_viewer(v, current_user)


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="视频详情",
    description=(
        "公开 `published` 任意访问；非发布态仅作者或管理员可见，"
        "其他情况统一返回 404（不暴露资源存在）。"
        "响应含 `Cache-Control`、`Vary: Authorization`（非发布态随身份变化）。"
        "支持 `If-None-Match` 与 `ETag`：未变化时返回 304。"
        "**VOD 绑定细节**：`vod_video_id`、`source_file_name` 仅 **作者或管理员** 可见，其它身份为 `null`；"
        "ETag 随可见性分层变化，避免登录前后误用 304。"
    ),
    responses=VIDEO_DETAIL_GET_RESPONSES,
)
def get_video(
    request: Request,
    response: Response,
    db: DbSession,
    video_id: uuid.UUID,
    optional_user: OptionalUser,
) -> VideoResponse | Response:
    v = video_service.get_video(db, video_id, optional_user)
    etag = weak_etag_for_video(v, vod_detail_tier=video_privacy.vod_detail_etag_tier(v, optional_user))
    if if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": MUTABLE_GET_CACHE_CONTROL,
                "Vary": "Authorization",
            },
        )
    response.headers["Cache-Control"] = MUTABLE_GET_CACHE_CONTROL
    response.headers["Vary"] = "Authorization"
    response.headers["ETag"] = etag
    return video_privacy.video_response_for_viewer(v, optional_user)


@router.patch(
    "/{video_id}",
    response_model=VideoResponse,
    summary="更新视频",
    description=(
        "仅作者或管理员。"
        "**作者自行下架**：对已发布（`published`）且本人为作者的资源，可通过本接口 PATCH `status` 为 `offline`（自愿下线，非平台处罚）。"
        "**管理员平台下架**：管理员对「已发布」视频的平台侧下线请使用 **POST** `/videos/{video_id}/offline`，勿用 PATCH 改状态。"
        "其余 `status` 变更须走审核专用 POST（提交审核 / 通过 / 驳回等）；管理员可将 `rejected` 打回 `draft` 以便作者再改。"
        "可带 `Idempotency-Key` 防止重复 PATCH。"
    ),
    responses=VIDEO_PATCH_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def update_video(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    body: VideoUpdate,
    idempotency_key: IdempotencyKeyHeader = None,
) -> VideoResponse:
    return run_idempotent_video_patch(
        actor_id=str(current_user.id),
        video_id=video_id,
        body=body,
        idempotency_key=idempotency_key,
        execute=lambda: video_service.update_video(db, current_user, video_id, body),
    )


@router.delete(
    "/{video_id}",
    status_code=204,
    summary="管理员删除视频",
    description="**仅管理员**。物理删除数据库记录及本机封面/成片文件；关联评论、点赞等由外键级联删除。不自动删除云端 VOD 媒资。",
    dependencies=[Depends(set_mutation_cache_control)],
)
def delete_video_admin(db: DbSession, admin: AdminUser, video_id: uuid.UUID) -> Response:
    video_service.admin_delete_video(db, admin, video_id)
    return Response(status_code=204)


@router.patch(
    "/{video_id}/bind-vod",
    response_model=VideoResponse,
    summary="绑定阿里云 VOD 媒资",
    description=(
        "需登录。**作者或管理员**可将本地稿件与阶段 11.1 获取的 **VOD VideoId** 绑定。"
        "同一 VideoId 全局仅能绑定一条稿件；**已绑定**时普通用户不可覆盖，**管理员**可改绑。"
        "普通用户创建稿件时不可直接写 `vod_video_id`，须使用本接口。"
        "可带 `Idempotency-Key`：与 PATCH 视频一致，24h 内相同 Key + 相同 JSON 体重放。"
    ),
    responses=VIDEO_BIND_VOD_PATCH_RESPONSES,
    dependencies=[Depends(set_mutation_cache_control)],
)
def bind_vod_video(
    db: DbSession,
    current_user: CurrentUser,
    video_id: uuid.UUID,
    body: VideoBindVodRequest,
    idempotency_key: IdempotencyKeyHeader = None,
) -> VideoResponse:
    return run_idempotent_video_bind_vod(
        actor_id=str(current_user.id),
        video_id=video_id,
        body=body,
        idempotency_key=idempotency_key,
        execute=lambda: video_service.bind_vod_to_video(db, current_user, video_id, body),
    )
