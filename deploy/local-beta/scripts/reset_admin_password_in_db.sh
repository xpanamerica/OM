#!/usr/bin/env bash
# 将「首个管理员」账号（admin@example.com 或 admin）的登录密码更新为环境变量中的明文。
# 仅用于本机 Beta：改 .env 里的 FIRST_SUPERUSER_PASSWORD 不会自动改库里旧哈希，可运行本脚本同步。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PASS="${ADMIN_RESET_PASSWORD:-admin2026}"
export ADMIN_RESET_PASSWORD="$PASS"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml exec -T \
  -e ADMIN_RESET_PASSWORD \
  api python -c "
import os
from app.db.session import SessionLocal
from app.repositories import user_repository
from app.core.security import get_password_hash, verify_password

pwd = os.environ['ADMIN_RESET_PASSWORD']
db = SessionLocal()
try:
    u = user_repository.get_by_email(db, 'admin@example.com')
    if not u:
        u = user_repository.get_by_username(db, 'admin')
    if not u:
        raise SystemExit('未找到 admin@example.com 或用户名为 admin 的账号，请先正常启动过一次 API')
    u.hashed_password = get_password_hash(pwd)
    db.add(u)
    db.commit()
    assert verify_password(pwd, u.hashed_password)
    print('[reset-admin] 已更新管理员密码，请用当前 FIRST_SUPERUSER 邮箱/用户名 + 新密码登录管理端。')
finally:
    db.close()
"
