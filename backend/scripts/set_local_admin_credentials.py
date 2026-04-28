#!/usr/bin/env python3
"""将「首个活跃管理员」的用户名与密码更新为指定值（本机 / Docker 内一次性运维用）。

用法（在 backend/ 下，需能连上 DATABASE_URL 所指库）：
  ./.venv/bin/python scripts/set_local_admin_credentials.py --username xixiang2026 --password '你的密码'

Docker 内：
  docker compose exec api python scripts/set_local_admin_credentials.py --username xixiang2026 --password '你的密码'
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 保证以仓库 backend/ 为根时可导入 app
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--username", required=True, help="新用户名")
    p.add_argument("--password", required=True, help="新明文密码（须符合注册用户策略）")
    args = p.parse_args()

    from sqlalchemy import select

    from app.core.security import get_password_hash
    from app.db.session import SessionLocal
    from app.models.enums import UserRole
    from app.models.user import User
    from app.repositories import user_repository

    username = args.username.strip()
    password = args.password
    if len(username) < 2:
        raise SystemExit("用户名至少 2 个字符")
    if len(password) < 8:
        raise SystemExit("密码至少 8 个字符")

    db = SessionLocal()
    try:
        other = user_repository.get_by_username(db, username)
        stmt = (
            select(User)
            .where(
                User.deleted_at.is_(None),
                User.role == UserRole.ADMIN,
                User.is_active == True,  # noqa: E712
            )
            .order_by(User.created_at.asc())
            .limit(1)
        )
        admin = db.execute(stmt).scalar_one_or_none()
        if admin is None:
            raise SystemExit("未找到活跃管理员用户；请先通过 FIRST_SUPERUSER_* 首启创建管理员。")

        if other is not None and other.id != admin.id:
            raise SystemExit(f"用户名「{username}」已被其他用户使用")

        admin.username = username
        admin.hashed_password = get_password_hash(password)
        admin.role = UserRole.ADMIN
        db.add(admin)
        db.commit()
        print(f"已更新管理员：username={admin.username!r} email={admin.email!r} id={admin.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
