#!/usr/bin/env bash
# 在已激活 media_app 的 shell 中执行（推荐：用仓库根 .vscode 默认终端打开 backend/ 后）：
#   bash scripts/verify_skeleton.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export SECRET_KEY="${SECRET_KEY:-unit-test-environment-default-secret-48b-min-ok!!}"
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
PY="${MEDIA_APP_PYTHON:-python}"
echo ">>> using: $($PY -c 'import sys; print(sys.executable)')"
$PY -m pytest -q --tb=short
$PY -m compileall -q app
$PY -c "from app.main import app; print('import_ok', app.title)"
echo ">>> skeleton verify OK"
