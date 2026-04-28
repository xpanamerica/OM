"""视频写接口幂等（Idempotency-Key）封装，避免路由层重复样板代码。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Header

from app.core.exceptions import AppError
from app.core.video_codes import (
    VIDEO_IDEMPOTENCY_BACKEND_UNAVAILABLE,
    VIDEO_IDEMPOTENCY_CONFLICT,
)
from app.infrastructure.idempotency_store import (
    idempotency_resolve,
    idempotency_store,
    stable_json_hash,
)
from app.models.video import Video
from app.schemas.video import VideoBindVodRequest, VideoCreate, VideoResponse, VideoUpdate

IdempotencyKeyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description="可选；24h 内相同 Key + 相同 JSON 体重放时返回首次成功响应；体变化则 409。",
        max_length=128,
    ),
]


def _idem_conflict() -> None:
    raise AppError(
        "幂等键已与不同的请求体绑定",
        status_code=409,
        code=VIDEO_IDEMPOTENCY_CONFLICT,
    )


def _idem_unavailable() -> None:
    raise AppError(
        "幂等存储暂不可用（需 Redis 且已关闭内存回退）",
        status_code=503,
        code=VIDEO_IDEMPOTENCY_BACKEND_UNAVAILABLE,
    )


def run_idempotent_video_create(
    *,
    actor_id: str,
    body: VideoCreate,
    idempotency_key: str | None,
    execute: Callable[[], Video],
) -> VideoResponse:
    if not idempotency_key:
        return VideoResponse.model_validate(execute())

    fp = stable_json_hash(body.model_dump(mode="json"))
    action, replay_body = idempotency_resolve(
        scope="video:create",
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
    )
    if action == "unavailable":
        _idem_unavailable()
    if action == "conflict":
        _idem_conflict()
    if action == "replay" and replay_body is not None:
        return VideoResponse.model_validate(replay_body)

    out = VideoResponse.model_validate(execute())
    idempotency_store(
        scope="video:create",
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
        status=201,
        body=out.model_dump(mode="json"),
    )
    return out


def run_idempotent_video_patch(
    *,
    actor_id: str,
    video_id: uuid.UUID,
    body: VideoUpdate,
    idempotency_key: str | None,
    execute: Callable[[], Video],
) -> VideoResponse:
    if not idempotency_key:
        return VideoResponse.model_validate(execute())

    fp = stable_json_hash(body.model_dump(mode="json", exclude_unset=True))
    scope = f"video:patch:{video_id}"
    action, replay_body = idempotency_resolve(
        scope=scope,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
    )
    if action == "unavailable":
        _idem_unavailable()
    if action == "conflict":
        _idem_conflict()
    if action == "replay" and replay_body is not None:
        return VideoResponse.model_validate(replay_body)

    out = VideoResponse.model_validate(execute())
    idempotency_store(
        scope=scope,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
        status=200,
        body=out.model_dump(mode="json"),
    )
    return out


def run_idempotent_video_bind_vod(
    *,
    actor_id: str,
    video_id: uuid.UUID,
    body: VideoBindVodRequest,
    idempotency_key: str | None,
    execute: Callable[[], Video],
) -> VideoResponse:
    if not idempotency_key:
        return VideoResponse.model_validate(execute())

    fp = stable_json_hash(body.model_dump(mode="json"))
    scope = f"video:bind-vod:{video_id}"
    action, replay_body = idempotency_resolve(
        scope=scope,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
    )
    if action == "unavailable":
        _idem_unavailable()
    if action == "conflict":
        _idem_conflict()
    if action == "replay" and replay_body is not None:
        return VideoResponse.model_validate(replay_body)

    out = VideoResponse.model_validate(execute())
    idempotency_store(
        scope=scope,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        body_fingerprint=fp,
        status=200,
        body=out.model_dump(mode="json"),
    )
    return out
