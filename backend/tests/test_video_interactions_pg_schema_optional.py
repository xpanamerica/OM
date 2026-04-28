"""可选：在已执行 ``alembic upgrade head`` 的 PostgreSQL 上校验点赞/收藏/播放记录表结构。

设置环境变量 ``VIDEO_INTERACTION_PG_SCHEMA_URL``（须以 postgresql 开头）后运行；
默认跳过，不占用 CI 主流程。仅做只读 introspection，不执行迁移、不写数据。
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text


def _pg_schema_url() -> str:
    return os.environ.get("VIDEO_INTERACTION_PG_SCHEMA_URL", "").strip()


@pytest.mark.skipif(
    not _pg_schema_url().lower().startswith("postgresql"),
    reason="可选：export VIDEO_INTERACTION_PG_SCHEMA_URL=postgresql+psycopg://...（库已 migration head）",
)
def test_postgresql_video_interactions_tables_and_constraints():
    url = _pg_schema_url()
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            for tbl in ("video_likes", "video_favorites", "view_records"):
                exists = conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = current_schema() AND table_name = :t)"
                    ),
                    {"t": tbl},
                ).scalar()
                assert exists is True, f"当前 schema 下缺少表 {tbl}"

        insp = inspect(eng)
        for tbl, uq_name in (
            ("video_likes", "uq_video_likes_user_video"),
            ("video_favorites", "uq_video_favorites_user_video"),
            ("view_records", "uq_view_records_user_video"),
        ):
            ucs = insp.get_unique_constraints(tbl)
            by_name = {uc["name"]: uc["column_names"] for uc in ucs}
            assert uq_name in by_name, f"PG {tbl}: 缺少唯一约束 {uq_name}，现有 {list(by_name)}"
            assert list(by_name[uq_name]) == ["user_id", "video_id"]
            fks = insp.get_foreign_keys(tbl)
            referred = {fk["referred_table"] for fk in fks}
            assert referred == {"users", "videos"}, f"PG {tbl}: 外键引用异常 {referred}"
    finally:
        eng.dispose()
