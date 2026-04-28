from __future__ import annotations

import sqlite3
import uuid
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeAlias

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.core.config as app_config
from app.core import upload_security
from app.core.exceptions import AppError
from app.core.video_cursor import decode_workflow_audit_cursor, encode_workflow_audit_cursor
from app.core.video_codes import (
    VIDEO_APPROVE_FORBIDDEN,
    VIDEO_BIND_VOD_FORBIDDEN,
    VIDEO_CATEGORY_NOT_FOUND,
    VIDEO_CREATE_FAILED,
    VIDEO_DELETE_FORBIDDEN,
    VIDEO_EDIT_FORBIDDEN,
    VIDEO_LIST_CURSOR_OFFSET_CONFLICT,
    VIDEO_LIST_FOLLOW_FEED_REQUIRES_AUTH,
    VIDEO_LIST_INVALID_CURSOR,
    VIDEO_NOT_FOUND,
    VIDEO_OFFLINE_FORBIDDEN,
    VIDEO_PLAY_OFFLINE_FORBIDDEN,
    VIDEO_SEARCH_INVALID_SORT,
    VIDEO_REJECT_FORBIDDEN,
    VIDEO_SEARCH_KEYWORD_TOO_LONG,
    VIDEO_STATUS_QUERY_FORBIDDEN,
    VIDEO_SUBMIT_FORBIDDEN,
    VIDEO_TAG_NOT_FOUND,
    VIDEO_VOD_ALREADY_BOUND,
    VIDEO_VOD_FIELDS_PATCH_FORBIDDEN,
    VIDEO_VOD_ID_CONFLICT,
    VIDEO_VOD_ID_CREATE_FORBIDDEN,
    VIDEO_WORKFLOW_EVENTS_FORBIDDEN,
)
from app.domain.video_workflow_rules import (
    WorkflowPostKind,
    assert_patch_status_change_allowed,
    assert_workflow_post_source_status,
    workflow_event_action,
    workflow_post_target,
)
from app.models.enums import UserRole, VideoStatus, VodTranscodeStatus, VodUploadStatus
from app.models.tag import Tag
from app.models.user import User
from app.models.video import Video
from app.models.video_workflow_event import VideoWorkflowEvent
from app.repositories import (
    category_repository,
    tag_repository,
    video_repository,
    video_workflow_event_repository,
)
from app.schemas.video import VideoBindVodRequest, VideoCreate, VideoRejectRequest, VideoUpdate
from app.services import algorithm_reset_service, app_settings_service
from app.services.video_list import run_video_list


@dataclass(frozen=True)
class AlgorithmFactor:
    label: str
    value: float
    weight: float


RecommendationReason: TypeAlias = tuple[dict[str, int], str]


def _dedupe_ids(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(ids))


def _load_tags_or_error(db: Session, tag_ids: list[uuid.UUID]) -> list[Tag]:
    uids = _dedupe_ids(tag_ids)
    if not uids:
        return []
    rows = tag_repository.list_by_ids(db, uids)
    if len(rows) != len(uids):
        raise AppError("包含不存在的标签", status_code=400, code=VIDEO_TAG_NOT_FOUND)
    return rows


def _is_vod_video_id_unique_violation(exc: IntegrityError) -> bool:
    """并发下预检查与提交之间可能竞态：依赖唯一索引并在提交时映射为业务 409。"""
    orig = getattr(exc, "orig", exc)
    if getattr(orig, "pgcode", None) == "23505":
        msg = str(orig).lower()
        return "vod_video_id" in msg or "uq_videos_vod_video_id" in msg
    if isinstance(orig, sqlite3.IntegrityError):
        msg = str(orig).lower()
        return "uq_videos_vod_video_id" in msg or "videos.vod_video_id" in msg
    msg = str(exc).lower()
    return "uq_videos_vod_video_id" in msg or "videos.vod_video_id" in msg


def _commit_video_mutation(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if _is_vod_video_id_unique_violation(e):
            raise AppError(
                "该 VOD VideoId 已被其它稿件占用",
                status_code=409,
                code=VIDEO_VOD_ID_CONFLICT,
            ) from None
        raise


def create_video(db: Session, actor: User, payload: VideoCreate) -> Video:
    upload_security.assert_video_text_and_cover_ok(
        title=payload.title,
        description=payload.description,
        cover_url=payload.cover_url,
    )
    upload_security.assert_source_file_name_extension_ok(payload.source_file_name)

    if payload.category_id is not None:
        if category_repository.get_by_id(db, payload.category_id) is None:
            raise AppError("分类不存在", status_code=400, code=VIDEO_CATEGORY_NOT_FOUND)
    tags = _load_tags_or_error(db, payload.tag_ids)

    vod_id: str | None = payload.vod_video_id
    if vod_id:
        if actor.role != UserRole.ADMIN:
            raise AppError(
                "普通用户创建稿件时不能指定 vod_video_id，请创建后使用 PATCH /videos/{video_id}/bind-vod",
                status_code=403,
                code=VIDEO_VOD_ID_CREATE_FORBIDDEN,
            )
        if video_repository.find_id_by_vod_video_id(db, vod_id) is not None:
            raise AppError("该 VOD VideoId 已被其它稿件占用", status_code=409, code=VIDEO_VOD_ID_CONFLICT)
        up_st = VodUploadStatus.PENDING
        tc_st = VodTranscodeStatus.PENDING
    else:
        vod_id = None
        up_st = VodUploadStatus.NOT_STARTED
        tc_st = VodTranscodeStatus.NONE

    v = video_repository.create(
        db,
        title=payload.title,
        description=payload.description,
        cover_url=payload.cover_url,
        video_url=payload.video_url,
        author_id=actor.id,
        category_id=payload.category_id,
        status=VideoStatus.DRAFT,
        tags=tags,
        vod_video_id=vod_id,
        upload_status=up_st,
        transcode_status=tc_st,
        duration_seconds=payload.duration_seconds,
        source_file_name=payload.source_file_name,
    )
    _commit_video_mutation(db)
    out = video_repository.get_by_id(db, v.id, load_tags=True)
    if out is None:
        raise AppError("视频创建失败", status_code=500, code=VIDEO_CREATE_FAILED)
    return out


def can_view_video(video: Video, viewer: User | None) -> bool:
    if video.status == VideoStatus.PUBLISHED:
        return True
    if viewer is None:
        return False
    if viewer.role == UserRole.ADMIN:
        return True
    return video.author_id == viewer.id


def assert_vod_play_permission(video: Video, viewer: User) -> None:
    """阶段 11.3：获取播放凭证的权限（与详情可见性独立：已发布须登录；下线仅作者/管理员）。"""
    if video.status == VideoStatus.OFFLINE:
        if viewer.role != UserRole.ADMIN and video.author_id != viewer.id:
            raise AppError(
                "视频已下线，无法获取播放凭证",
                status_code=403,
                code=VIDEO_PLAY_OFFLINE_FORBIDDEN,
            )
        return
    if video.status == VideoStatus.PUBLISHED:
        return
    if viewer.role == UserRole.ADMIN or video.author_id == viewer.id:
        return
    raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)


def _origin_freshness_score(video: Video, *, now: datetime) -> float:
    ref = video.published_at or video.created_at
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_days = max((now - ref).total_seconds() / 86_400, 0.0)
    return max(0.0, 1.0 - min(age_days, 30.0) / 30.0)


def _stable_random_factor(*, seed: str, mode: str, page: int, video_id: uuid.UUID) -> float:
    digest = hashlib.sha256(f"{seed}:mode:{mode}:page:{page}:{video_id}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16)).random()


def _video_algorithm_signals(
    video: Video,
    *,
    max_quality: int,
    now: datetime,
    seed: str,
    mode: str,
    page: int,
) -> dict[str, float]:
    random_factor = _stable_random_factor(seed=seed, mode=mode, page=page, video_id=video.id)
    quality = _normalized_engagement(video, max_quality=max_quality)
    freshness = _origin_freshness_score(video, now=now)
    depth = min(((video.duration_seconds or 0) / 900.0) + (0.2 if video.description else 0.0), 1.0)
    entertainment = min((video.likes_count + video.favorites_count * 2) / max(video.views_count + 1, 1), 1.0)
    novelty = max(0.0, min(1.0, 1.0 - freshness * 0.35 + random_factor * 0.65))
    challenge = max(0.0, min(1.0, depth * 0.7 + novelty * 0.3))
    diversity = 0.7 + (0.3 if video.category_id is not None else 0.0)
    return {
        "random": random_factor,
        "quality": quality,
        "freshness": freshness,
        "depth": depth,
        "entertainment": entertainment,
        "novelty": novelty,
        "challenge": challenge,
        "diversity": diversity,
    }


def _normalized_custom_parameters(parameters: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, fallback in {
        "randomness": 50,
        "diversity": 70,
        "depth": 50,
        "entertainment": 50,
        "challenge": 50,
        "novelty": 60,
    }.items():
        raw = parameters.get(key, fallback)
        try:
            out[key] = max(0, min(int(raw), 100)) / 100
        except (TypeError, ValueError):
            out[key] = fallback / 100
    return out


def _algorithm_factors_for_video(
    video: Video,
    *,
    mode: str,
    parameters: dict,
    seed: str,
    page: int,
    max_quality: int,
    now: datetime,
) -> list[AlgorithmFactor]:
    s = _video_algorithm_signals(video, max_quality=max_quality, now=now, seed=seed, mode=mode, page=page)
    if mode == "origin":
        return [
            AlgorithmFactor("随机探索", s["random"], 0.5),
            AlgorithmFactor("内容质量", s["quality"], 0.3),
            AlgorithmFactor("时间新鲜度", s["freshness"], 0.2),
        ]
    if mode == "efficiency":
        return [
            AlgorithmFactor("信息密度", s["quality"], 0.34),
            AlgorithmFactor("学习价值", s["depth"], 0.28),
            AlgorithmFactor("目标匹配", (s["quality"] + s["freshness"]) / 2, 0.22),
            AlgorithmFactor("随机校准", s["random"], 0.08),
            AlgorithmFactor("多样补偿", s["diversity"], 0.08),
        ]
    if mode == "growth":
        return [
            AlgorithmFactor("认知挑战", s["challenge"], 0.34),
            AlgorithmFactor("内容深度", s["depth"], 0.24),
            AlgorithmFactor("新颖性", s["novelty"], 0.22),
            AlgorithmFactor("跨域多样", s["diversity"], 0.12),
            AlgorithmFactor("质量评分", s["quality"], 0.08),
        ]
    if mode == "emotion":
        return [
            AlgorithmFactor("娱乐沉浸", s["entertainment"], 0.4),
            AlgorithmFactor("时间新鲜度", s["freshness"], 0.18),
            AlgorithmFactor("随机探索", s["random"], 0.24),
            AlgorithmFactor("质量评分", s["quality"], 0.1),
            AlgorithmFactor("多样缓冲", s["diversity"], 0.08),
        ]
    if mode == "custom":
        p = _normalized_custom_parameters(parameters)
        return [
            AlgorithmFactor("随机性", s["random"], p["randomness"] * 0.18),
            AlgorithmFactor("多样性", s["diversity"], p["diversity"] * 0.16),
            AlgorithmFactor("深度", s["depth"], p["depth"] * 0.18),
            AlgorithmFactor("娱乐性", s["entertainment"], p["entertainment"] * 0.14),
            AlgorithmFactor("认知挑战", s["challenge"], p["challenge"] * 0.18),
            AlgorithmFactor("新颖性", s["novelty"], p["novelty"] * 0.16),
            AlgorithmFactor("质量底座", s["quality"], 0.08),
        ]
    return [
        AlgorithmFactor("综合质量", s["quality"], 0.5),
        AlgorithmFactor("时间新鲜度", s["freshness"], 0.3),
        AlgorithmFactor("基础探索", s["random"], 0.2),
    ]


def _score_from_factors(factors: list[AlgorithmFactor]) -> float:
    return sum(max(0.0, factor.value) * max(0.0, factor.weight) for factor in factors)


def _reason_from_factors(factors: list[AlgorithmFactor]) -> RecommendationReason:
    contributions = [(factor.label, max(0.0, factor.value) * max(0.0, factor.weight)) for factor in factors]
    total = sum(value for _, value in contributions)
    if total <= 0:
        reason = {factors[0].label if factors else "基础探索": 100}
    else:
        raw = [(label, value / total * 100) for label, value in contributions if value > 0]
        rounded = [(label, int(value)) for label, value in raw]
        remainder = 100 - sum(value for _, value in rounded)
        fractions = sorted(
            ((idx, raw[idx][1] - rounded[idx][1]) for idx in range(len(raw))),
            key=lambda item: item[1],
            reverse=True,
        )
        values = [value for _, value in rounded]
        for idx, _ in fractions[: max(0, remainder)]:
            values[idx] += 1
        reason = {raw[idx][0]: values[idx] for idx in range(len(raw)) if values[idx] > 0}
    text = "为什么推荐你：" + "，".join(f"{key} {value}%" for key, value in reason.items())
    return reason, text


def _origin_feed_order(videos: list[Video], *, seed: str, page: int, offset: int, limit: int) -> list[Video]:
    if not videos:
        return []
    max_quality = max(
        (v.views_count + v.likes_count * 4 + v.favorites_count * 6 for v in videos),
        default=1,
    ) or 1
    now = datetime.now(timezone.utc)
    scored: list[tuple[float, Video]] = []
    for video in videos:
        factors = _algorithm_factors_for_video(
            video,
            mode="origin",
            parameters={},
            seed=seed,
            page=page,
            max_quality=max_quality,
            now=now,
        )
        scored.append((_score_from_factors(factors), video))
    remaining = sorted(scored, key=lambda item: item[0], reverse=True)
    ordered: list[Video] = []
    last_author: uuid.UUID | None = None
    last_category: uuid.UUID | None = None
    while remaining:
        pick_idx = 0
        for idx, (_, candidate) in enumerate(remaining):
            if candidate.author_id != last_author and candidate.category_id != last_category:
                pick_idx = idx
                break
        _, picked = remaining.pop(pick_idx)
        ordered.append(picked)
        last_author = picked.author_id
        last_category = picked.category_id
    return ordered[offset : offset + limit]


def _normalized_engagement(video: Video, *, max_quality: int) -> float:
    return (video.views_count + video.likes_count * 4 + video.favorites_count * 6) / max(max_quality, 1)


def _algorithm_feed_order(
    videos: list[Video],
    *,
    mode: str,
    parameters: dict,
    seed: str,
    page: int,
    offset: int,
    limit: int,
) -> list[Video]:
    if mode == "origin":
        return _origin_feed_order(videos, seed=seed, page=page, offset=offset, limit=limit)
    if not videos:
        return []
    max_quality = max((v.views_count + v.likes_count * 4 + v.favorites_count * 6 for v in videos), default=1) or 1
    now = datetime.now(timezone.utc)
    scored: list[tuple[float, Video]] = []
    for video in videos:
        factors = _algorithm_factors_for_video(
            video,
            mode=mode,
            parameters=parameters,
            seed=seed,
            page=page,
            max_quality=max_quality,
            now=now,
        )
        scored.append((_score_from_factors(factors), video))
    return [video for _, video in sorted(scored, key=lambda item: item[0], reverse=True)][offset : offset + limit]


def _recommendation_reasons_for_items(
    items: list[Video],
    *,
    mode: str,
    parameters: dict,
    seed: str,
    page: int,
    pool: list[Video] | None = None,
) -> dict[uuid.UUID, RecommendationReason]:
    if not items:
        return {}
    score_pool = pool or items
    max_quality = max((v.views_count + v.likes_count * 4 + v.favorites_count * 6 for v in score_pool), default=1) or 1
    now = datetime.now(timezone.utc)
    reasons: dict[uuid.UUID, RecommendationReason] = {}
    for video in items:
        factors = _algorithm_factors_for_video(
            video,
            mode=mode,
            parameters=parameters,
            seed=seed,
            page=page,
            max_quality=max_quality,
            now=now,
        )
        reasons[video.id] = _reason_from_factors(factors)
    return reasons


def _origin_feed_pool(
    db: Session,
    *,
    viewer_id: uuid.UUID,
    offset: int,
    limit: int,
) -> list[Video]:
    pool_limit = max(offset + limit * 12, 100)
    pool = video_repository.list_videos(
        db,
        offset=0,
        limit=pool_limit,
        only_published=True,
        status=None,
        category_id=None,
        tag_id=None,
        author_id=None,
        follower_id_for_following=None,
    )
    return [video for video in pool if video.author_id != viewer_id]


def get_video(db: Session, video_id: uuid.UUID, viewer: User | None) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, viewer):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    return v


def list_videos(
    db: Session,
    viewer: User | None,
    *,
    offset: int,
    limit: int,
    cursor: str | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    status: VideoStatus | None,
    author_id: uuid.UUID | None,
    follower_id_for_following: uuid.UUID | None = None,
) -> tuple[list[Video], int, bool]:
    if follower_id_for_following is not None and viewer is None:
        raise AppError(
            "关注流需登录",
            status_code=401,
            code=VIDEO_LIST_FOLLOW_FEED_REQUIRES_AUTH,
        )
    is_admin = viewer is not None and viewer.role == UserRole.ADMIN
    if not is_admin and status is not None:
        raise AppError(
            "非管理员不能使用 status 查询参数",
            status_code=400,
            code=VIDEO_STATUS_QUERY_FORBIDDEN,
        )
    only_published = not is_admin
    eff_status = status if is_admin else None

    total = video_repository.count_videos(
        db,
        only_published=only_published,
        status=eff_status,
        category_id=category_id,
        tag_id=tag_id,
        author_id=author_id,
        follower_id_for_following=follower_id_for_following,
    )

    if (
        viewer is not None
        and not is_admin
        and follower_id_for_following is None
        and cursor is None
        and status is None
        and category_id is None
        and tag_id is None
        and author_id is None
        and algorithm_reset_service.is_origin_mode(db, user_id=viewer.id)
    ):
        state = algorithm_reset_service.get_algorithm_state(db, user_id=viewer.id) or {}
        seed = str(state.get("explorationSeed") or viewer.id)
        page = max(offset // max(limit, 1) + 1, 1)
        pool = _origin_feed_pool(
            db,
            viewer_id=viewer.id,
            offset=offset,
            limit=limit,
        )
        return _origin_feed_order(pool, seed=seed, page=page, offset=offset, limit=limit), len(pool), len(pool) > offset + limit

    def fetch_all(db_sess: Session, *, limit: int, offset: int) -> list[Video]:
        return video_repository.list_videos(
            db_sess,
            offset=offset,
            limit=limit,
            only_published=only_published,
            status=eff_status,
            category_id=category_id,
            tag_id=tag_id,
            author_id=author_id,
            follower_id_for_following=follower_id_for_following,
        )

    def fetch_after(
        db_sess: Session,
        *,
        after_created_at: datetime,
        after_id: uuid.UUID,
        limit: int,
    ) -> list[Video]:
        return video_repository.list_videos_after(
            db_sess,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=limit,
            only_published=only_published,
            status=eff_status,
            category_id=category_id,
            tag_id=tag_id,
            author_id=author_id,
            follower_id_for_following=follower_id_for_following,
        )

    items, has_more = run_video_list(
        db,
        fetch_all=fetch_all,
        fetch_after=fetch_after,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )
    return items, total, has_more


def list_feed_videos(
    db: Session,
    viewer: User | None,
    *,
    offset: int,
    limit: int,
    page: int,
) -> tuple[list[Video], int, bool, str, bool, str | None, dict[uuid.UUID, RecommendationReason]]:
    if viewer is not None and algorithm_reset_service.is_origin_mode(db, user_id=viewer.id):
        state = algorithm_reset_service.get_algorithm_state(db, user_id=viewer.id) or {}
        seed = str(state.get("explorationSeed") or viewer.id)
        pool = _origin_feed_pool(db, viewer_id=viewer.id, offset=offset, limit=limit)
        mode = "origin"
        params = state.get("parameters") if isinstance(state.get("parameters"), dict) else {}
        items = _algorithm_feed_order(pool, mode=mode, parameters=params, seed=seed, page=page, offset=offset, limit=limit)
        reasons = _recommendation_reasons_for_items(
            items,
            mode=mode,
            parameters=params,
            seed=seed,
            page=page,
            pool=pool,
        )
        return (
            items,
            len(pool),
            len(pool) > offset + limit,
            mode,
            False,
            "归源模式已开启：你正在随机、多元地重新探索世界。",
            reasons,
        )

    if viewer is not None:
        state = algorithm_reset_service.get_algorithm_state(db, user_id=viewer.id) or {}
        mode = str(state.get("mode") or "personalized")
        if mode in {"efficiency", "growth", "emotion", "custom"}:
            seed = str(state.get("explorationSeed") or viewer.id)
            params = state.get("parameters") if isinstance(state.get("parameters"), dict) else {}
            pool = _origin_feed_pool(db, viewer_id=viewer.id, offset=offset, limit=limit)
            items = _algorithm_feed_order(pool, mode=mode, parameters=params, seed=seed, page=page, offset=offset, limit=limit)
            reasons = _recommendation_reasons_for_items(
                items,
                mode=mode,
                parameters=params,
                seed=seed,
                page=page,
                pool=pool,
            )
            explanation = {
                "efficiency": "效率模式已开启：优先呈现信息密度、学习价值和目标匹配更高的内容。",
                "growth": "成长模式已开启：系统会更多推送有价值但不完全熟悉的内容，帮助你突破舒适区。",
                "emotion": "情绪模式已开启：内容会更偏放松、娱乐和沉浸体验。",
                "custom": "自定义模式已开启：推荐会按照你的参数权重运行。",
            }[mode]
            return items, len(pool), len(pool) > offset + limit, mode, True, explanation, reasons

    items, total, has_more = list_videos(
        db,
        viewer,
        offset=offset,
        limit=limit,
        cursor=None,
        category_id=None,
        tag_id=None,
        status=None,
        author_id=None,
        follower_id_for_following=None,
    )
    reasons = _recommendation_reasons_for_items(
        items,
        mode="personalized",
        parameters={},
        seed=str(viewer.id) if viewer is not None else "anonymous",
        page=page,
        pool=items,
    )
    return items, total, has_more, "personalized", True, None, reasons


def recommendation_reason(*, mode: str, video: Video) -> tuple[dict[str, int], str]:
    reasons = _recommendation_reasons_for_items(
        [video],
        mode=mode,
        parameters={},
        seed="fallback",
        page=1,
        pool=[video],
    )
    return reasons[video.id]


def record_feed_attention(db: Session, *, viewer: User | None, mode: str, items: list[Video]) -> None:
    algorithm_reset_service.record_attention_snapshot(db, user=viewer, mode=mode, videos=items)
    if viewer is not None and items:
        db.commit()


_SEARCH_SORT_CANON = frozenset({"latest", "views", "likes"})


def search_videos(
    db: Session,
    viewer: User | None,
    *,
    keyword: str | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    sort_by: str,
    offset: int,
    limit: int,
) -> tuple[list[Video], int]:
    """阶段 13：数据库级搜索；非管理员仅 ``published``，管理员可命中全部状态。"""
    if keyword is not None:
        ks = keyword.strip()
        lim = int(app_config.settings.VIDEO_SEARCH_KEYWORD_MAX_LENGTH)
        if len(ks) > lim:
            raise AppError(
                f"关键词长度超过上限（{lim} 字符）",
                status_code=400,
                code=VIDEO_SEARCH_KEYWORD_TOO_LONG,
            )

    sb = (sort_by or "latest").strip().lower()
    if sb not in _SEARCH_SORT_CANON:
        raise AppError("sort_by 须为 latest、views 或 likes", status_code=400, code=VIDEO_SEARCH_INVALID_SORT)
    if category_id is not None and category_repository.get_by_id(db, category_id) is None:
        raise AppError("分类不存在", status_code=400, code=VIDEO_CATEGORY_NOT_FOUND)
    if tag_id is not None and tag_repository.get_by_id(db, tag_id) is None:
        raise AppError("标签不存在", status_code=400, code=VIDEO_TAG_NOT_FOUND)

    is_admin = viewer is not None and viewer.role == UserRole.ADMIN
    only_published = not is_admin
    total = video_repository.count_search_videos(
        db,
        keyword=keyword,
        category_id=category_id,
        tag_id=tag_id,
        only_published=only_published,
    )
    items = video_repository.search_videos(
        db,
        keyword=keyword,
        category_id=category_id,
        tag_id=tag_id,
        sort_by=sb,
        only_published=only_published,
        offset=offset,
        limit=limit,
    )
    return items, total


def list_trending_videos(db: Session, *, offset: int, limit: int) -> tuple[list[Video], int]:
    """阶段 13：仅已发布；按 views/likes/favorites 加权热度排序。"""
    total = video_repository.count_trending_videos(db)
    items = video_repository.list_trending_videos(db, offset=offset, limit=limit)
    return items, total


def list_latest_videos(db: Session, *, offset: int, limit: int) -> tuple[list[Video], int]:
    """阶段 13：仅已发布，按创建时间倒序。"""
    total = video_repository.count_latest_videos(db)
    items = video_repository.list_latest_videos(db, offset=offset, limit=limit)
    return items, total


def _assert_can_edit(video: Video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id != actor.id:
        raise AppError("无权编辑该视频", status_code=403, code=VIDEO_EDIT_FORBIDDEN)


def _touch_published_at_if_newly_published(video: Video, old: VideoStatus, new: VideoStatus) -> None:
    if new == VideoStatus.PUBLISHED and old != VideoStatus.PUBLISHED and video.published_at is None:
        video.published_at = datetime.now(timezone.utc)


def _reload_video_after_commit(db: Session, video_id: uuid.UUID) -> Video:
    out = video_repository.get_by_id(db, video_id, load_tags=True)
    if out is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    return out


def update_video(db: Session, actor: User, video_id: uuid.UUID, payload: VideoUpdate) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_can_edit(v, actor)

    data = payload.model_dump(exclude_unset=True)
    vod_only_keys = {"upload_status", "transcode_status", "duration_seconds", "source_file_name"}
    if actor.role != UserRole.ADMIN and vod_only_keys & data.keys():
        raise AppError(
            "仅管理员可通过 PATCH 修改 upload_status / transcode_status / duration_seconds / source_file_name",
            status_code=403,
            code=VIDEO_VOD_FIELDS_PATCH_FORBIDDEN,
        )
    if not data:
        return v

    if any(k in data for k in ("title", "description", "cover_url")):
        new_title = data["title"] if "title" in data else v.title
        new_desc = data["description"] if "description" in data else v.description
        new_cover = data["cover_url"] if "cover_url" in data else v.cover_url
        upload_security.assert_video_text_and_cover_ok(
            title=new_title,
            description=new_desc,
            cover_url=new_cover,
        )
    if "source_file_name" in data:
        upload_security.assert_source_file_name_extension_ok(data["source_file_name"])

    old_status = v.status

    if "status" in data:
        assert_patch_status_change_allowed(old_status, data["status"], actor.role)

    if "title" in data:
        v.title = data["title"]
    if "description" in data:
        v.description = data["description"]
    if "cover_url" in data:
        v.cover_url = data["cover_url"]
    if "video_url" in data:
        v.video_url = data["video_url"]
    if "category_id" in data:
        cid = data["category_id"]
        if cid is not None and category_repository.get_by_id(db, cid) is None:
            raise AppError("分类不存在", status_code=400, code=VIDEO_CATEGORY_NOT_FOUND)
        v.category_id = cid
    if "status" in data:
        new_s = data["status"]
        v.status = new_s
        _touch_published_at_if_newly_published(v, old_status, new_s)
    if "tag_ids" in data and data["tag_ids"] is not None:
        tags = _load_tags_or_error(db, data["tag_ids"])
        video_repository.replace_video_tags(db, v, tags)
    if "upload_status" in data and data["upload_status"] is not None:
        v.upload_status = data["upload_status"]
    if "transcode_status" in data and data["transcode_status"] is not None:
        v.transcode_status = data["transcode_status"]
    if "duration_seconds" in data:
        v.duration_seconds = data["duration_seconds"]
    if "source_file_name" in data:
        v.source_file_name = data["source_file_name"]

    # 保证 ETag / 条件 GET 语义：部分环境下 ORM onupdate 与同一时刻写入可能不推进时间戳
    v.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _reload_video_after_commit(db, video_id)


def bind_vod_to_video(db: Session, actor: User, video_id: uuid.UUID, body: VideoBindVodRequest) -> Video:
    """作者或管理员将本地稿件与阿里云 VOD ``VideoId`` 绑定。

    MVP 规则：
    - 全局同一 ``vod_video_id`` 最多绑定一条本地稿件（部分唯一索引）。
    - 已绑定情况下：普通用户不可覆盖；**管理员**可改绑（运维纠错 / 迁移）。
    - 不在此接口调用阿里云校验归属；防「随意绑定他人资源」依赖：普通用户不能在创建时写
      ``vod_video_id``，且绑定仅限本人稿件 + 全局唯一约束。
    """
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if not can_view_video(v, actor):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if actor.role != UserRole.ADMIN and v.author_id != actor.id:
        raise AppError("仅作者或管理员可绑定 VOD 媒资", status_code=403, code=VIDEO_BIND_VOD_FORBIDDEN)

    new_id = body.vod_video_id
    other = video_repository.find_id_by_vod_video_id(db, new_id, exclude_video_id=video_id)
    if other is not None:
        raise AppError("该 VOD VideoId 已被其它稿件占用", status_code=409, code=VIDEO_VOD_ID_CONFLICT)

    if v.vod_video_id and actor.role != UserRole.ADMIN:
        raise AppError(
            "该稿件已绑定 VOD 媒资，普通用户不可覆盖；需改绑请联系管理员",
            status_code=409,
            code=VIDEO_VOD_ALREADY_BOUND,
        )

    if body.source_file_name is not None:
        upload_security.assert_source_file_name_extension_ok(body.source_file_name)

    v.vod_video_id = new_id
    v.upload_status = body.upload_status or VodUploadStatus.PENDING
    v.transcode_status = body.transcode_status or VodTranscodeStatus.PENDING
    if body.duration_seconds is not None:
        v.duration_seconds = body.duration_seconds
    if body.source_file_name is not None:
        v.source_file_name = body.source_file_name
    v.updated_at = datetime.now(timezone.utc)
    _commit_video_mutation(db)
    return _reload_video_after_commit(db, video_id)


def _assert_author_or_admin(video: Video, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if video.author_id != actor.id:
        raise AppError("仅作者或管理员可提交审核", status_code=403, code=VIDEO_SUBMIT_FORBIDDEN)


def submit_video_for_review(db: Session, actor: User, video_id: uuid.UUID) -> Video:
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    _assert_author_or_admin(v, actor)
    assert_workflow_post_source_status(WorkflowPostKind.SUBMIT_REVIEW, v.status)
    old = v.status
    publish_without_review = app_settings_service.is_video_publish_without_review_enabled(db)
    next_status = VideoStatus.PUBLISHED if publish_without_review else workflow_post_target(WorkflowPostKind.SUBMIT_REVIEW)
    v.status = next_status
    v.rejection_reason = None
    if next_status == VideoStatus.PUBLISHED and v.published_at is None:
        v.published_at = datetime.now(timezone.utc)
    v.updated_at = datetime.now(timezone.utc)
    video_workflow_event_repository.append_event(
        db,
        video_id=video_id,
        actor_id=actor.id,
        action=workflow_event_action(WorkflowPostKind.SUBMIT_REVIEW),
        from_status=old.value,
        to_status=next_status.value,
        detail={"auto_published_by_setting": True} if publish_without_review else None,
    )
    db.commit()
    return _reload_video_after_commit(db, video_id)


def approve_video(db: Session, actor: User, video_id: uuid.UUID) -> Video:
    if actor.role != UserRole.ADMIN:
        raise AppError("需要管理员权限", status_code=403, code=VIDEO_APPROVE_FORBIDDEN)
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    assert_workflow_post_source_status(WorkflowPostKind.APPROVE, v.status)
    old = v.status
    next_status = workflow_post_target(WorkflowPostKind.APPROVE)
    v.status = next_status
    v.rejection_reason = None
    if v.published_at is None:
        v.published_at = datetime.now(timezone.utc)
    v.updated_at = datetime.now(timezone.utc)
    video_workflow_event_repository.append_event(
        db,
        video_id=video_id,
        actor_id=actor.id,
        action=workflow_event_action(WorkflowPostKind.APPROVE),
        from_status=old.value,
        to_status=next_status.value,
    )
    db.commit()
    return _reload_video_after_commit(db, video_id)


def reject_video(db: Session, actor: User, video_id: uuid.UUID, payload: VideoRejectRequest) -> Video:
    if actor.role != UserRole.ADMIN:
        raise AppError("需要管理员权限", status_code=403, code=VIDEO_REJECT_FORBIDDEN)
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    assert_workflow_post_source_status(WorkflowPostKind.REJECT, v.status)
    old = v.status
    next_status = workflow_post_target(WorkflowPostKind.REJECT)
    v.status = next_status
    v.rejection_reason = payload.rejection_reason
    v.updated_at = datetime.now(timezone.utc)
    video_workflow_event_repository.append_event(
        db,
        video_id=video_id,
        actor_id=actor.id,
        action=workflow_event_action(WorkflowPostKind.REJECT),
        from_status=old.value,
        to_status=next_status.value,
        detail={"rejection_reason": payload.rejection_reason},
    )
    db.commit()
    return _reload_video_after_commit(db, video_id)


def offline_video_by_admin(db: Session, actor: User, video_id: uuid.UUID) -> Video:
    if actor.role != UserRole.ADMIN:
        raise AppError("需要管理员权限", status_code=403, code=VIDEO_OFFLINE_FORBIDDEN)
    v = video_repository.get_by_id(db, video_id, load_tags=True)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    assert_workflow_post_source_status(WorkflowPostKind.OFFLINE_ADMIN, v.status)
    old = v.status
    next_status = workflow_post_target(WorkflowPostKind.OFFLINE_ADMIN)
    v.status = next_status
    v.updated_at = datetime.now(timezone.utc)
    video_workflow_event_repository.append_event(
        db,
        video_id=video_id,
        actor_id=actor.id,
        action=workflow_event_action(WorkflowPostKind.OFFLINE_ADMIN),
        from_status=old.value,
        to_status=next_status.value,
    )
    db.commit()
    return _reload_video_after_commit(db, video_id)


def admin_delete_video(db: Session, actor: User, video_id: uuid.UUID) -> None:
    """管理员物理删除稿件及本机封面/成片文件（不调用云厂商删除 VOD 媒资）。"""
    if actor.role != UserRole.ADMIN:
        raise AppError("需要管理员权限", status_code=403, code=VIDEO_DELETE_FORBIDDEN)
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None:
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)

    from app.services import local_video_media_service
    from app.services.video_cover_service import cover_file_path

    local_video_media_service.unlink_local_stored_media_by_relpath(v.local_video_relpath)
    try:
        cover_file_path(video_id).unlink(missing_ok=True)
    except OSError:
        pass

    db.delete(v)
    _commit_video_mutation(db)


def list_video_workflow_events(
    db: Session,
    actor: User,
    video_id: uuid.UUID,
    *,
    offset: int,
    limit: int,
    cursor: str | None,
) -> tuple[list[VideoWorkflowEvent], int, bool, str | None]:
    """按视频列出工作流审计（`created_at`+`audit_sequence` 正序）：管理员任意；作者仅本人稿件。

    `cursor` 使用 `decode_workflow_audit_cursor`；续页游标由 `encode_workflow_audit_cursor` 写入响应头。
    """
    v = video_repository.get_by_id(db, video_id, load_tags=False)
    if v is None or not can_view_video(v, actor):
        raise AppError("视频不存在", status_code=404, code=VIDEO_NOT_FOUND)
    if actor.role != UserRole.ADMIN and v.author_id != actor.id:
        raise AppError("无权查看该视频的工作流审计", status_code=403, code=VIDEO_WORKFLOW_EVENTS_FORBIDDEN)

    if cursor and cursor.strip():
        if offset != 0:
            raise AppError(
                "不能同时使用 offset 与 cursor",
                status_code=400,
                code=VIDEO_LIST_CURSOR_OFFSET_CONFLICT,
            )
        try:
            after_created_at, after_audit_sequence = decode_workflow_audit_cursor(cursor.strip())
        except ValueError as e:
            raise AppError("无效的 cursor", status_code=400, code=VIDEO_LIST_INVALID_CURSOR) from e
        total = video_workflow_event_repository.count_for_video(db, video_id=video_id)
        raw = video_workflow_event_repository.list_after_cursor(
            db,
            video_id=video_id,
            after_created_at=after_created_at,
            after_audit_sequence=after_audit_sequence,
            limit=limit + 1,
        )
        has_more = len(raw) > limit
        page = raw[:limit]
        next_cursor: str | None = None
        if has_more and page:
            last = page[-1]
            next_cursor = encode_workflow_audit_cursor(
                created_at=last.created_at, audit_sequence=last.audit_sequence
            )
        return page, total, has_more, next_cursor

    rows, total = video_workflow_event_repository.list_page_by_video_id(
        db, video_id=video_id, offset=offset, limit=limit + 1
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_workflow_audit_cursor(
            created_at=last.created_at, audit_sequence=last.audit_sequence
        )
    return page, total, has_more, next_cursor
