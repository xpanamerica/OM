#!/usr/bin/env bash
# PostgreSQL 逻辑备份（单机 cron 或运维手工执行）
# 依赖：本机已安装 pg_dump（postgresql-client），或在与库互通的网络内执行。
#
# 必填环境变量：POSTGRES_USER、POSTGRES_PASSWORD、POSTGRES_DB
# 可选：POSTGRES_HOST（默认 127.0.0.1）、POSTGRES_PORT（默认 5432）、BACKUP_ROOT（默认 ./backups）
set -euo pipefail

: "${POSTGRES_USER:?set POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}"
: "${POSTGRES_DB:?set POSTGRES_DB}"

POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"

mkdir -p "${BACKUP_ROOT}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_GZ="${BACKUP_ROOT}/${POSTGRES_DB}_${STAMP}.sql.gz"

export PGHOST="${POSTGRES_HOST}"
export PGPORT="${POSTGRES_PORT}"
export PGUSER="${POSTGRES_USER}"
export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGDATABASE="${POSTGRES_DB}"

echo "[backup] dumping ${POSTGRES_DB} @ ${POSTGRES_HOST}:${POSTGRES_PORT} -> ${OUT_GZ}"
pg_dump --no-owner --no-acl | gzip -9 > "${OUT_GZ}"
echo "[backup] done size=$(du -h "${OUT_GZ}" | cut -f1)"
