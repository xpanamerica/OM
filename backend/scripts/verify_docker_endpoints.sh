#!/usr/bin/env bash
# 在 `docker compose up -d` 成功且 api 监听 8000 后执行，校验 HTTP 与数据库字段。
# 若刚启动容器，Uvicorn 可能尚未就绪，会短暂重试（避免误报「连接被重置」）。
#
# 可选：设置 VERIFY_DOCKER_AUTH=1 时，额外校验默认首个管理员 OAuth 登录与 GET /users/me。
# 默认管理员密码由 scripts/read_compose_first_superuser_password.py 解析（优先 backend/.env，
# 其次环境变量，再回退 compose 中 FIRST_SUPERUSER_PASSWORD 的 :- 默认段）；若与容器内不一致，
# 请设置 DOCKER_FIRST_SUPERUSER_PASSWORD 与容器内实际值一致。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND_DIR}"

BASE="${1:-http://127.0.0.1:8000}"
HEALTH_URL="${BASE%/}/health"
DOCS_URL="${BASE%/}/docs"
OPENAPI_URL="${BASE%/}/openapi.json"
API_PREFIX="${BASE%/}/api/v1"

HEALTH_JSON="$(mktemp)"
trap 'rm -f "${HEALTH_JSON}"' EXIT

try_curl() {
  local url="$1"
  local out="$2"
  # -4：强制 IPv4，避免部分环境 localhost 解析到 ::1 与映射不一致
  curl -4 -sS --connect-timeout 3 --max-time 30 -o "$out" -w '%{http_code}' "$url" 2>/dev/null || echo "000"
}

wait_for_health() {
  local code="" i
  for i in $(seq 1 45); do
    code="$(try_curl "${HEALTH_URL}" "${HEALTH_JSON}")"
    if [[ "${code}" == "200" ]]; then
      echo ">>> GET ${HEALTH_URL} → HTTP ${code}（第 ${i} 次尝试成功）"
      return 0
    fi
    echo ">>> 等待 api 就绪… (${i}/45) HTTP ${code}"
    sleep 2
  done
  echo
  echo "[FAIL] 多次重试后仍无法 GET /health（常见：api 容器内进程崩溃或仍在启动）。"
  echo "请执行："
  echo "  docker compose ps -a"
  echo "  docker compose logs api --tail 200"
  exit 1
}

echo ">>> GET ${HEALTH_URL}（含就绪重试）"
wait_for_health
cat "${HEALTH_JSON}"
echo

echo ">>> GET ${DOCS_URL}"
code="$(try_curl "${DOCS_URL}" /dev/null)"
echo "HTTP ${code}"
test "${code}" = "200"

echo ">>> GET ${OPENAPI_URL}"
code="$(try_curl "${OPENAPI_URL}" /dev/null)"
echo "HTTP ${code}"
test "${code}" = "200"

echo ">>> 期望 health JSON 中 database=connected（compose 默认 postgres/redis 均就绪时应为 ok）"
export _VD_HEALTH_JSON="${HEALTH_JSON}"
python3 - <<'PY'
import json, os, sys

path = os.environ["_VD_HEALTH_JSON"]
with open(path) as f:
    d = json.load(f)
print(d)
if d.get("database") != "connected":
    sys.exit("database 非 connected，请检查 DATABASE_URL 与 db 容器日志")
if d.get("status") not in ("ok", "degraded"):
    sys.exit("status 异常")
PY
unset _VD_HEALTH_JSON 2>/dev/null || true

if [[ "${VERIFY_DOCKER_AUTH:-0}" == "1" ]]; then
  echo ">>> VERIFY_DOCKER_AUTH=1：校验 POST /api/v1/auth/login 与 GET /api/v1/users/me"
  _default_super_pw="$(python3 "${SCRIPT_DIR}/read_compose_first_superuser_password.py")"
  PW="${DOCKER_FIRST_SUPERUSER_PASSWORD:-${_default_super_pw}}"
  LOGIN_TMP="$(mktemp)"
  trap 'rm -f "${HEALTH_JSON}" "${LOGIN_TMP}"' EXIT
  LOGIN_HTTP="$(curl -4 -sS --max-time 30 -o "${LOGIN_TMP}" -w '%{http_code}' -X POST "${API_PREFIX}/auth/login" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "username=admin" \
    --data-urlencode "password=${PW}")"
  if [[ "${LOGIN_HTTP}" != "200" ]]; then
    echo "[FAIL] POST /auth/login HTTP ${LOGIN_HTTP}" >&2
    head -c 2000 "${LOGIN_TMP}" >&2 || true
    echo >&2
    exit 1
  fi
  export _VD_LOGIN_JSON_PATH="${LOGIN_TMP}"
  export _VD_API_PREFIX="${API_PREFIX}"
  python3 - <<'PY'
import json, os, subprocess, sys

path = os.environ["_VD_LOGIN_JSON_PATH"]
api = os.environ["_VD_API_PREFIX"]
with open(path) as f:
    raw = f.read()
try:
    body = json.loads(raw)
except json.JSONDecodeError as e:
    print("[FAIL] /auth/login 响应非 JSON:", e, file=sys.stderr)
    print("[FAIL] 原始响应前 1200 字符:", repr(raw[:1200]), file=sys.stderr)
    raise SystemExit(1)
if "access_token" not in body:
    print("[FAIL] /auth/login 未包含 access_token:", repr(raw[:1200]), file=sys.stderr)
    raise SystemExit(1)
tok = body["access_token"]

p = subprocess.run(
    [
        "curl",
        "-4",
        "-sS",
        "--max-time",
        "30",
        f"{api}/users/me",
        "-H",
        f"Authorization: Bearer {tok}",
    ],
    capture_output=True,
    text=True,
)
if p.returncode != 0:
    print("[FAIL] GET /users/me curl 失败:", p.stderr, file=sys.stderr)
    raise SystemExit(1)
try:
    me = json.loads(p.stdout)
except json.JSONDecodeError as e:
    print("[FAIL] /users/me 非 JSON:", e, file=sys.stderr)
    print("[FAIL] 原始:", repr(p.stdout[:1200]), file=sys.stderr)
    raise SystemExit(1)
if me.get("username") != "admin":
    print("[FAIL] /users/me 用户名异常:", me, file=sys.stderr)
    raise SystemExit(1)
print(">>> docker auth smoke OK (admin /me)")
PY
  unset _VD_LOGIN_JSON_PATH _VD_API_PREFIX 2>/dev/null || true
fi

echo ">>> verify_docker_endpoints OK"
