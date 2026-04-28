"""在临时 SQLite 文件上跑完整 Alembic 链，防止迁移仅适配 PostgreSQL 而回归。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _assert_video_interaction_tables(con: sqlite3.Connection) -> None:
    for tbl, uq_name in (
        ("video_likes", "uq_video_likes_user_video"),
        ("video_favorites", "uq_video_favorites_user_video"),
    ):
        assert (
            con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tbl,),
            ).fetchone()
            is not None
        ), f"upgrade head 后须存在 {tbl} 表"
        ddl_row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,),
        ).fetchone()
        assert ddl_row is not None
        ddl = ddl_row[0]
        assert uq_name in ddl, f"{tbl} 须含具名唯一约束 {uq_name}"
        assert "UNIQUE (user_id, video_id)" in ddl, f"{tbl} DDL 须显式 UNIQUE(user_id, video_id)"
        fks = con.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()
        ref_tables = {row[2] for row in fks}
        assert ref_tables == {"users", "videos"}, f"{tbl} 外键应仅指向 users/videos: {ref_tables}"
        uniq_indexes = [
            row
            for row in con.execute(f"PRAGMA index_list({tbl})").fetchall()
            if len(row) >= 3 and row[2] == 1 and row[3] == "u"
        ]
        assert uniq_indexes, f"{tbl} 须存在 UNIQUE 索引（origin=u）"


def _assert_view_records_table(con: sqlite3.Connection) -> None:
    tbl, uq_name = "view_records", "uq_view_records_user_video"
    assert (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,),
        ).fetchone()
        is not None
    ), f"upgrade head 后须存在 {tbl} 表"
    ddl_row = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
    assert ddl_row is not None
    ddl = ddl_row[0]
    assert uq_name in ddl
    assert "UNIQUE (user_id, video_id)" in ddl
    assert "progress_seconds >= 0" in ddl.replace(" ", "").lower() or "progress_seconds>=" in ddl.replace(" ", "")


def _assert_video_interaction_schema_via_sqlalchemy_inspector(database_url: str) -> None:
    """与具体方言无关：唯一约束名与列顺序、外键引用表（与 PostgreSQL 迁移结果对齐）。"""
    eng = create_engine(database_url)
    try:
        insp = inspect(eng)
        for tbl, uq_name in (
            ("video_likes", "uq_video_likes_user_video"),
            ("video_favorites", "uq_video_favorites_user_video"),
        ):
            ucs = insp.get_unique_constraints(tbl)
            names = {uc["name"]: uc["column_names"] for uc in ucs}
            assert uq_name in names, f"{tbl}: 期望唯一约束 {uq_name}，实际 {list(names)}"
            assert list(names[uq_name]) == ["user_id", "video_id"]
            fks = insp.get_foreign_keys(tbl)
            referred = {fk["referred_table"] for fk in fks}
            assert referred == {"users", "videos"}, f"{tbl}: 外键引用表应为 users+videos: {referred}"
        ucs = insp.get_unique_constraints("view_records")
        vnames = {uc["name"]: uc["column_names"] for uc in ucs}
        assert "uq_view_records_user_video" in vnames
        assert list(vnames["uq_view_records_user_video"]) == ["user_id", "video_id"]
        vfk = insp.get_foreign_keys("view_records")
        assert {fk["referred_table"] for fk in vfk} == {"users", "videos"}
    finally:
        eng.dispose()


def _assert_sqlite_unique_rejects_duplicate_pair(con: sqlite3.Connection) -> None:
    """数据库层：同一 (user_id, video_id) 第二条 INSERT 须失败。"""
    con.execute("PRAGMA foreign_keys=ON")
    uid, vid = uuid.uuid4().hex, uuid.uuid4().hex
    lid1, lid2 = uuid.uuid4().hex, uuid.uuid4().hex
    fid1, fid2 = uuid.uuid4().hex, uuid.uuid4().hex
    email = f"{uid[:12]}@alembic-uniq.example"
    username = f"u{uid[:10]}"
    con.execute(
        "INSERT INTO users (id,email,username,hashed_password) VALUES (?,?,?,?)",
        (uid, email, username, "h"),
    )
    con.execute(
        "INSERT INTO videos (id,title,author_id,status) VALUES (?,?,?,?)",
        (vid, "t", uid, "published"),
    )
    con.execute(
        "INSERT INTO video_likes (id,user_id,video_id) VALUES (?,?,?)",
        (lid1, uid, vid),
    )
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        con.execute(
            "INSERT INTO video_likes (id,user_id,video_id) VALUES (?,?,?)",
            (lid2, uid, vid),
        )
    assert "UNIQUE" in str(excinfo.value).upper()

    con.execute(
        "INSERT INTO video_favorites (id,user_id,video_id) VALUES (?,?,?)",
        (fid1, uid, vid),
    )
    with pytest.raises(sqlite3.IntegrityError) as excinfo2:
        con.execute(
            "INSERT INTO video_favorites (id,user_id,video_id) VALUES (?,?,?)",
            (fid2, uid, vid),
        )
    assert "UNIQUE" in str(excinfo2.value).upper()

    con.execute("DELETE FROM video_favorites WHERE id=?", (fid1,))
    con.execute("DELETE FROM video_likes WHERE id=?", (lid1,))
    con.execute("DELETE FROM videos WHERE id=?", (vid,))
    con.execute("DELETE FROM users WHERE id=?", (uid,))
    con.commit()


def test_alembic_upgrade_head_sqlite_file(tmp_path):
    db_file = tmp_path / "alembic_chain.db"
    # 绝对路径：sqlite:/// + /abs → 共四个斜杠（SQLAlchemy 约定）
    database_url = "sqlite:///" + db_file.resolve().as_posix()

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["SECRET_KEY"] = "a" * 48

    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"

    con = sqlite3.connect(db_file)
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='comments'"
        )
        assert cur.fetchone() is not None, "upgrade head 后须存在 comments 表"
        fks = con.execute("PRAGMA foreign_key_list(comments)").fetchall()
        ref_tables = {row[2] for row in fks}
        assert "videos" in ref_tables and "users" in ref_tables, f"comments 外键异常: {fks}"

        _assert_video_interaction_tables(con)
        _assert_view_records_table(con)
        _assert_sqlite_unique_rejects_duplicate_pair(con)
    finally:
        con.close()

    _assert_video_interaction_schema_via_sqlalchemy_inspector(database_url)

    r2 = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0003_users_role"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r2.returncode == 0, f"stdout:\n{r2.stdout}\nstderr:\n{r2.stderr}"
