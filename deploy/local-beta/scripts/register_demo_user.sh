#!/usr/bin/env bash
# 内测：注册一名普通用户（非管理员）。管理员依赖 FIRST_SUPERUSER_* 首启 init_db。
set -euo pipefail
BASE="${BETA_PUBLIC_BASE:-http://127.0.0.1:8080}"
EMAIL="${BETA_DEMO_EMAIL:-beta-demo@example.com}"
USER="${BETA_DEMO_USERNAME:-betademo}"
PASS="${BETA_DEMO_PASSWORD:-BetaDemo-user-pass-9chars}"

echo "[seed-user] POST ${BASE}/api/v1/auth/register"
code=$(curl -sS -o /tmp/beta_reg.json -w "%{http_code}" -X POST "${BASE}/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"username\":\"${USER}\",\"password\":\"${PASS}\"}" || true)
cat /tmp/beta_reg.json 2>/dev/null || true
echo
if [[ "$code" == "201" || "$code" == "200" ]]; then
  echo "[seed-user] OK ($code)"
elif [[ "$code" == "409" || "$code" == "422" ]]; then
  echo "[seed-user] 可能已注册或校验未通过 ($code)，可忽略"
else
  echo "[seed-user] 非预期 HTTP $code（请确认 Nginx 已起且 BASE 正确）" >&2
  exit 1
fi
