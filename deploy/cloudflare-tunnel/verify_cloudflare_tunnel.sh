#!/usr/bin/env bash
# 校验 Cloudflare Tunnel 后的用户站 / 管理端 / 同源 API 是否可用。
#
# 用法：
#   APP_URL=https://app.example.com ADMIN_URL=https://admin.example.com \
#     bash deploy/cloudflare-tunnel/verify_cloudflare_tunnel.sh
set -euo pipefail

APP_URL="${APP_URL:-}"
ADMIN_URL="${ADMIN_URL:-}"

if [[ -z "${APP_URL}" || -z "${ADMIN_URL}" ]]; then
  echo "用法：APP_URL=https://app.example.com ADMIN_URL=https://admin.example.com bash $0" >&2
  exit 2
fi

APP_URL="${APP_URL%/}"
ADMIN_URL="${ADMIN_URL%/}"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

curl_code() {
  local url="$1" out="$2"
  curl -sS --connect-timeout 8 --max-time 40 -o "$out" -w '%{http_code}' "$url"
}

expect_code() {
  local url="$1" want="$2" out="$3" code
  code="$(curl_code "$url" "$out")"
  echo ">>> ${url} -> HTTP ${code}"
  if [[ "${code}" != "${want}" ]]; then
    echo "[FAIL] 期望 HTTP ${want}，实际 ${code}；响应前 1200 字符：" >&2
    head -c 1200 "$out" >&2 || true
    echo >&2
    exit 1
  fi
}

echo ">>> 校验用户站首页"
expect_code "${APP_URL}/" "200" "${tmp}/app.html"
if ! grep -qi '<div id="app"\|/assets/' "${tmp}/app.html"; then
  echo "[FAIL] 用户站首页不像 Vite SPA 输出，请确认 user-web 已 npm run build 且 Nginx 挂载 dist。" >&2
  exit 1
fi

echo ">>> 校验管理端首页"
expect_code "${ADMIN_URL}/" "200" "${tmp}/admin.html"
if ! grep -qi '<div id="app"\|/assets/' "${tmp}/admin.html"; then
  echo "[FAIL] 管理端首页不像 Vite SPA 输出，请确认 admin-web 已 npm run build 且 Nginx 挂载 dist。" >&2
  exit 1
fi

echo ">>> 校验用户站同源 API /health"
expect_code "${APP_URL}/health" "200" "${tmp}/health.json"
python3 - "${tmp}/health.json" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as f:
    d = json.load(f)
print(d)
if d.get("database") != "connected":
    raise SystemExit("database 非 connected")
if d.get("status") not in ("ok", "degraded"):
    raise SystemExit("status 异常")
PY

echo ">>> 校验用户站 OpenAPI（说明 /api/v1 反代正常）"
expect_code "${APP_URL}/openapi.json" "200" "${tmp}/openapi.json"
python3 - "${tmp}/openapi.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
paths = d.get("paths") or {}
for p in ("/api/v1/auth/login", "/api/v1/videos/{video_id}/play", "/api/v1/videos/{video_id}/local-stream"):
    if p not in paths:
        raise SystemExit(f"OpenAPI 缺少 {p}，请确认 API_V1_PREFIX 与反代路径")
print("OpenAPI paths OK")
PY

echo ">>> 校验管理端同源 API /health"
expect_code "${ADMIN_URL}/health" "200" "${tmp}/admin-health.json"

echo ">>> verify_cloudflare_tunnel OK"
echo "提示：本机成片播放 URL 若仍是 http://，请在 backend/.env.local-beta 设置："
echo "  API_PUBLIC_BASE_URL=${APP_URL}/api/v1"
echo "并重启：docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml up -d --build"
