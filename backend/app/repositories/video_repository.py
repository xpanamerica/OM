from __future__ import annotations

import uuid
from datetime import datetime

import app.core.config as app_config
from sqlalchemy import Float, and_, cast, exists, func, literal, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import VideoStatus, VodTranscodeStatus, VodUploadStatus
from app.models.tag import Tag
from app.models.user_follow import UserFollow
from app.models.video import Video, video_tags


def get_by_vod_video_id(db: Session, vod_video_id: str) -> Video | None:
    vid = (vod_video_id or "").strip()
    if not vid:
        return None
    stmt = select(Video).where(Video.vod_video_id == vid)
    return db.execute(stmt).scalar_one_or_none()


def find_id_by_vod_video_id(
    db: Session,
    vod_video_id: str,
    *,
    exclude_video_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """若存在占用该 ``vod_video_id`` 的稿件则返回其主键（可选排除自身，供管理员改绑）。"""
    stmt = select(Video.id).where(Video.vod_video_id == vod_video_id)
    if exclude_video_id is not None:
        stmt = stmt.where(Video.id != exclude_video_id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, video_id: uuid.UUID, *, load_tags: bool = False) -> Video | None:
    stmt = select(Video).where(Video.id == video_id)
    if load_tags:
        stmt = stmt.options(selectinload(Video.tags))
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    title: str,
    description: str | None,
    cover_url: str | None,
    video_url: str | None,
    author_id: uuid.UUID,
    category_id: uuid.UUID | None,
    status: VideoStatus = VideoStatus.DRAFT,
    tags: list[Tag] | None = None,
    vod_video_id: str | None = None,
    upload_status: VodUploadStatus = VodUploadStatus.NOT_STARTED,
    transcode_status: VodTranscodeStatus = VodTranscodeStatus.NONE,
    duration_seconds: int | None = None,
    source_file_name: str | None = None,
) -> Video:
    row = Video(
        title=title,
        description=description,
        cover_url=cover_url,
        video_url=video_url,
        author_id=author_id,
        category_id=category_id,
        status=status,
        vod_video_id=vod_video_id,
        upload_status=upload_status,
        transcode_status=transcode_status,
        duration_seconds=duration_seconds,
        source_file_name=source_file_name,
    )
    if tags:
        row.tags = tags
    db.add(row)
    db.flush()
    return row


def _base_list_stmt():
    return select(Video).options(selectinload(Video.tags))


def _apply_list_filters(
    stmt,
    *,
    only_published: bool,
    status: VideoStatus | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    author_id: uuid.UUID | None,
    follower_id_for_following: uuid.UUID | None = None,
):
    """列表与 count 共用 WHERE，避免两处条件不一致。"""
    if only_published:
        stmt = stmt.where(Video.status == VideoStatus.PUBLISHED)
    elif status is not None:
        stmt = stmt.where(Video.status == status)
    if category_id is not None:
        stmt = stmt.where(Video.category_id == category_id)
    if author_id is not None:
        stmt = stmt.where(Video.author_id == author_id)
    if follower_id_for_following is not None:
        followees = select(UserFollow.followee_id).where(UserFollow.follower_id == follower_id_for_following)
        stmt = stmt.where(Video.author_id.in_(followees))
    if tag_id is not None:
        stmt = stmt.where(
            exists().where(
                (video_tags.c.video_id == Video.id) & (video_tags.c.tag_id == tag_id)
            )
        )
    return stmt


def _order_desc():
    return (Video.created_at.desc(), Video.id.desc())


def list_videos(
    db: Session,
    *,
    offset: int = 0,
    limit: int | None,
    only_published: bool,
    status: VideoStatus | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    author_id: uuid.UUID | None,
    follower_id_for_following: uuid.UUID | None = None,
) -> list[Video]:
    stmt = _apply_list_filters(
        _base_list_stmt(),
        only_published=only_published,
        status=status,
        category_id=category_id,
        tag_id=tag_id,
        author_id=author_id,
        follower_id_for_following=follower_id_for_following,
    ).order_by(*_order_desc())
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_videos_after(
    db: Session,
    *,
    after_created_at: datetime,
    after_id: uuid.UUID,
    limit: int,
    only_published: bool,
    status: VideoStatus | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    author_id: uuid.UUID | None,
    follower_id_for_following: uuid.UUID | None = None,
) -> list[Video]:
    keyset = or_(
        Video.created_at < after_created_at,
        and_(Video.created_at == after_created_at, Video.id < after_id),
    )
    stmt = (
        _apply_list_filters(
            _base_list_stmt(),
            only_published=only_published,
            status=status,
            category_id=category_id,
            tag_id=tag_id,
            author_id=author_id,
            follower_id_for_following=follower_id_for_following,
        )
        .where(keyset)
        .order_by(*_order_desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def count_videos(
    db: Session,
    *,
    only_published: bool,
    status: VideoStatus | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    author_id: uuid.UUID | None,
    follower_id_for_following: uuid.UUID | None = None,
) -> int:
    stmt = _apply_list_filters(
        select(func.count(Video.id)).select_from(Video),
        only_published=only_published,
        status=status,
        category_id=category_id,
        tag_id=tag_id,
        author_id=author_id,
        follower_id_for_following=follower_id_for_following,
    )
    return int(db.execute(stmt).scalar_one())


def replace_video_tags(db: Session, video: Video, tags: list[Tag]) -> None:
    video.tags = tags
    db.flush()


def _admin_title_keyword_clause(keyword: str | None):
    """标题模糊匹配；去掉 ``%`` / ``_`` 避免通配符注入。"""
    if not keyword or not keyword.strip():
        return None
    k = keyword.strip()[:200].replace("%", "").replace("_", "")
    if not k:
        return None
    return Video.title.ilike(f"%{k}%")


def _apply_admin_video_list_filters(
    stmt,
    *,
    status: VideoStatus | None,
    author_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    keyword: str | None,
):
    if status is not None:
        stmt = stmt.where(Video.status == status)
    if author_id is not None:
        stmt = stmt.where(Video.author_id == author_id)
    if category_id is not None:
        stmt = stmt.where(Video.category_id == category_id)
    kw = _admin_title_keyword_clause(keyword)
    if kw is not None:
        stmt = stmt.where(kw)
    return stmt


def list_videos_for_admin(
    db: Session,
    *,
    offset: int,
    limit: int,
    status: VideoStatus | None,
    author_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    keyword: str | None,
) -> list[Video]:
    stmt = _apply_admin_video_list_filters(
        _base_list_stmt(),
        status=status,
        author_id=author_id,
        category_id=category_id,
        keyword=keyword,
    ).order_by(*_order_desc())
    stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_videos_for_admin(
    db: Session,
    *,
    status: VideoStatus | None,
    author_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    keyword: str | None,
) -> int:
    stmt = _apply_admin_video_list_filters(
        select(func.count(Video.id)).select_from(Video),
        status=status,
        author_id=author_id,
        category_id=category_id,
        keyword=keyword,
    )
    return int(db.execute(stmt).scalar_one())


def aggregate_video_counter_totals(db: Session) -> tuple[int, int, int]:
    """返回 ``(sum(views_count), sum(likes_count), sum(favorites_count))``，无行时为 0。"""
    row = db.execute(
        select(
            func.coalesce(func.sum(Video.views_count), 0),
            func.coalesce(func.sum(Video.likes_count), 0),
            func.coalesce(func.sum(Video.favorites_count), 0),
        ).select_from(Video)
    ).one()
    return int(row[0]), int(row[1]), int(row[2])


def list_author_owned_videos_for_profile(
    db: Session,
    *,
    author_id: uuid.UUID,
    offset: int = 0,
    limit: int = 12,
) -> list[Video]:
    """作者本人个人中心：全部状态稿件，按更新时间倒序。"""
    stmt = (
        _base_list_stmt()
        .where(Video.author_id == author_id)
        .order_by(Video.updated_at.desc(), Video.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def sum_published_likes_and_favorites_on_author_videos(db: Session, *, author_id: uuid.UUID) -> int:
    """已发布稿件上累计获得的点赞 + 收藏次数。"""
    stmt = select(func.coalesce(func.sum(Video.likes_count + Video.favorites_count), 0)).where(
        Video.author_id == author_id,
        Video.status == VideoStatus.PUBLISHED,
    )
    return int(db.execute(stmt).scalar_one())


def count_videos_by_status(db: Session, *, status: VideoStatus) -> int:
    return int(
        db.scalar(select(func.count(Video.id)).select_from(Video).where(Video.status == status)) or 0
    )


def count_videos_total(db: Session) -> int:
    return int(db.scalar(select(func.count(Video.id)).select_from(Video)) or 0)


def _search_keyword_pattern(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    cap = int(app_config.settings.VIDEO_SEARCH_KEYWORD_MAX_LENGTH)
    k = str(raw).strip()[:cap].replace("%", "").replace("_", "")
    return f"%{k}%" if k else None


def _apply_search_visibility(stmt, *, only_published: bool):
    if only_published:
        return stmt.where(Video.status == VideoStatus.PUBLISHED)
    return stmt


def _apply_search_filters(
    stmt,
    *,
    keyword_pattern: str | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
):
    if keyword_pattern is not None:
        stmt = stmt.where(
            or_(Video.title.ilike(keyword_pattern), Video.description.ilike(keyword_pattern))
        )
    if category_id is not None:
        stmt = stmt.where(Video.category_id == category_id)
    if tag_id is not None:
        stmt = stmt.where(
            exists().where((video_tags.c.video_id == Video.id) & (video_tags.c.tag_id == tag_id))
        )
    return stmt


def _search_order_by(sort_by: str):
    s = (sort_by or "latest").strip().lower()
    if s == "views":
        return (Video.views_count.desc(), Video.id.desc())
    if s == "likes":
        return (Video.likes_count.desc(), Video.id.desc())
    return (Video.created_at.desc(), Video.id.desc())


def search_videos(
    db: Session,
    *,
    keyword: str | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    sort_by: str,
    only_published: bool,
    offset: int,
    limit: int,
) -> list[Video]:
    """标题 + 描述 ILIKE；PostgreSQL 生产可为 ``title``/``description`` 建 ``pg_trgm`` GIN 控制延迟。"""
    pat = _search_keyword_pattern(keyword)
    stmt = _apply_search_filters(_base_list_stmt(), keyword_pattern=pat, category_id=category_id, tag_id=tag_id)
    stmt = _apply_search_visibility(stmt, only_published=only_published)
    stmt = stmt.order_by(*_search_order_by(sort_by)).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_search_videos(
    db: Session,
    *,
    keyword: str | None,
    category_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    only_published: bool,
) -> int:
    pat = _search_keyword_pattern(keyword)
    stmt = select(func.count(Video.id)).select_from(Video)
    stmt = _apply_search_filters(stmt, keyword_pattern=pat, category_id=category_id, tag_id=tag_id)
    stmt = _apply_search_visibility(stmt, only_published=only_published)
    return int(db.execute(stmt).scalar_one())


def _trending_score_expr():
    """线性热度分；权重由 ``VIDEO_TRENDING_WEIGHT_*`` 配置（运营可调，无需改代码）。"""
    s = app_config.settings
    return (
        Video.views_count * int(s.VIDEO_TRENDING_WEIGHT_VIEWS)
        + Video.likes_count * int(s.VIDEO_TRENDING_WEIGHT_LIKES)
        + Video.favorites_count * int(s.VIDEO_TRENDING_WEIGHT_FAVORITES)
    )


def _trending_order_columns(db: Session):
    """返回 ``(主排序列, 次排序列)``；主列可为带时间衰减的有效热度（SQLite / PostgreSQL 分支）。"""
    base = _trending_score_expr()
    half = float(app_config.settings.VIDEO_TRENDING_RECENCY_HALF_LIFE_DAYS)
    if half <= 0:
        return base.desc(), Video.id.desc()

    ref = func.coalesce(Video.published_at, Video.created_at)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        age_days = cast(func.extract("epoch", func.now() - ref), Float) / literal(86400.0)
    else:
        age_days = literal_column(
            "(julianday('now') - julianday(coalesce(videos.published_at, videos.created_at)))"
        ).cast(Float)
    mult = literal(1.0) / (literal(1.0) + age_days / literal(half))
    effective = base * mult
    return effective.desc(), Video.id.desc()


def list_trending_videos(
    db: Session,
    *,
    offset: int,
    limit: int,
) -> list[Video]:
    o1, o2 = _trending_order_columns(db)
    stmt = (
        _base_list_stmt()
        .where(Video.status == VideoStatus.PUBLISHED)
        .order_by(o1, o2)
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def count_trending_videos(db: Session) -> int:
    return int(
        db.scalar(select(func.count(Video.id)).select_from(Video).where(Video.status == VideoStatus.PUBLISHED)) or 0
    )


def list_latest_videos(
    db: Session,
    *,
    offset: int,
    limit: int,
) -> list[Video]:
    stmt = (
        _base_list_stmt()
        .where(Video.status == VideoStatus.PUBLISHED)
        .order_by(Video.created_at.desc(), Video.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def count_latest_videos(db: Session) -> int:
    return count_trending_videos(db)
