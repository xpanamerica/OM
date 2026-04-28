#!/usr/bin/env bash
# 起完整 Compose 栈并做烟测：
#   - GET /health：HTTP 200 且 JSON 中 database=connected（Redis 偶发降级不判失败）
#   - GET /docs、GET /openapi.json：HTTP 200
# 用于 CI 或发布前自检；结束时 tear down 并删卷。
#
# 可选：export COMPOSE_FILE="docker-compose.yml:docker-compose.override.yml"
# 以叠加本机 override（勿将含密钥的 override 提交 Git）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND_DIR}"

export COMPOSE_HTTP_TIMEOUT="${COMPOSE_HTTP_TIMEOUT:-300}"
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

if [[ ! -f .env ]]; then
  echo "==> 未找到 backend/.env，生成本机随机密钥（scripts/init_local_compose_env.sh）…" >&2
  bash "${SCRIPT_DIR}/init_local_compose_env.sh"
fi

cleanup() {
  docker compose down -v --timeout 30 2>/dev/null || true
}
trap cleanup EXIT

echo "==> compose config (${COMPOSE_FILE})"
docker compose config --quiet

echo "==> up -d --build"
docker compose up -d --build

BASE="${SMOKE_BASE_URL:-http://127.0.0.1:8000}"
echo "==> wait for ${BASE}/health"

ok=0
health_body=""
for i in $(seq 1 90); do
  if health_body="$(curl -fsS "${BASE%/}/health" 2>/dev/null)"; then
    if python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d.get('database')=='connected' else 1)" "${health_body}" 2>/dev/null; then
      ok=1
      break
    fi
  fi
  sleep 2
done
if [[ "${ok}" -ne 1 ]]; then
  echo "timeout or /health JSON missing database=connected" >&2
  echo "last /health body: ${health_body:-<empty>}" >&2
  docker compose logs --tail 80 api >&2 || true
  exit 1
fi

echo "==> GET /docs"
code="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE%/}/docs")"
if [[ "${code}" != "200" ]]; then
  echo "expected /docs HTTP 200, got ${code}" >&2
  exit 1
fi

echo "==> GET /openapi.json"
code_o="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE%/}/openapi.json")"
if [[ "${code_o}" != "200" ]]; then
  echo "expected /openapi.json HTTP 200, got ${code_o}" >&2
  exit 1
fi

echo "==> smoke OK"
