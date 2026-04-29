#!/usr/bin/env bash
# 在 backend/ 下生成仅用于本机 Docker Compose 的 .env（随机 SECRET_KEY / 数据库口令 / 首管口令）。
# - 若 .env 已存在则 **不覆盖**（避免误删你的配置）；需重建时请自行备份后删除 .env 再执行。
# - 数据库口令仅含 [0-9a-f]，可安全嵌入 DATABASE_URL 而无需 URL 编码。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ -f .env ]]; then
  echo "init_local_compose_env: .env 已存在，未写入。删除或改名后再运行本脚本。" >&2
  exit 0
fi

SK="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
PP="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
FP="$(python3 -c "import secrets; print(secrets.token_hex(12))")"

cat > .env <<EOF
# 由 scripts/init_local_compose_env.sh 自动生成（本机 Compose 专用，勿提交 Git）
COMPOSE_HTTP_TIMEOUT=300
MEDIA_POSTGRES_IMAGE=docker.m.daocloud.io/library/postgres:16-alpine
MEDIA_REDIS_IMAGE=docker.m.daocloud.io/library/redis:7-alpine
MEDIA_PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim

POSTGRES_USER=postgres
POSTGRES_PASSWORD=${PP}
POSTGRES_DB=videodb

SECRET_KEY=${SK}
DATABASE_URL=postgresql+psycopg://postgres:${PP}@db:5432/videodb
REDIS_URL=redis://redis:6379/0

ENVIRONMENT=local
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1
ACCESS_TOKEN_EXPIRE_MINUTES=60
AUTH_RATE_LIMIT_ENABLED=true
AUTH_RATE_LIMIT_USE_REDIS=true
AUTH_RATE_LIMIT_REDIS_FALLBACK_MEMORY=true

FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_PASSWORD=${FP}
EOF

chmod 600 .env 2>/dev/null || true
echo "init_local_compose_env: 已写入 ${ROOT}/.env（权限已尽量设为 600）。" >&2
