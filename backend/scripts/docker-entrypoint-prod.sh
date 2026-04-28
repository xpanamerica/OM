#!/bin/sh
# 生产入口：迁移后启动 Gunicorn + Uvicorn worker（单机 ECS 常见形态）
set -e
cd /app

echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

WEB_CONCURRENCY="${WEB_CONCURRENCY:-4}"
PORT="${PORT:-8000}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

echo "[entrypoint] starting gunicorn workers=${WEB_CONCURRENCY} bind=0.0.0.0:${PORT}"
exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY}" \
  --bind "0.0.0.0:${PORT}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  "$@"
