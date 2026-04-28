#!/usr/bin/env bash
# 在已激活的 Conda 环境 media_app（或任意目标环境）的终端中执行：
#   bash "/home/xixiang2025/OM/backend/scripts/install_requirements_in_env.sh"
#
# 使用当前 shell 的 python（请确认 prompt 为 (media_app) 且 which python 指向 envs/media_app）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQ="${BACKEND}/requirements.txt"

cd "${BACKEND}"

echo ">>> 使用解释器: $(command -v python)"
python -V

echo ">>> 升级 pip…"
python -m pip install -U pip setuptools wheel

echo ">>> 安装 requirements.txt …"
python -m pip install -r "${REQ}"

echo ">>> 校验应用可导入（使用占位环境变量，不连库）…"
export SECRET_KEY="${SECRET_KEY:-dev-verify-secret-key-default-48-chars-minimum-length!!}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@127.0.0.1:5432/videodb}"
python -c "from app.main import app; print('import_ok', app.title)"

echo ">>> 依赖安装完成。"
echo "    启动前请在 backend 目录准备 .env 或 export SECRET_KEY / DATABASE_URL / REDIS_URL，"
echo "    并确保 PostgreSQL 与 Redis 可用（例如 docker compose up -d db redis）。"
