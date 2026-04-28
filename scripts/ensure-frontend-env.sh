#!/usr/bin/env bash
# 确保 user-web / admin-web 存在 .env.local，且含合法 VITE_API_BASE_URL（避免 curl/axios 无 host）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 与 docker-compose.local-beta 的 Nginx 同源（用户站 :8080 / 管理端 :8081）；须先启动 local-beta
for app in user-web admin-web; do
  if [[ "$app" == "admin-web" ]]; then
    LINE='VITE_API_BASE_URL=http://127.0.0.1:8081/api/v1'
  else
    LINE='VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1'
  fi
  d="${ROOT}/${app}"
  f="${d}/.env.local"
  if [[ ! -f "$f" ]]; then
    cp "${d}/.env.example" "$f"
    echo "[ensure-frontend-env] 已创建 ${f}"
  fi
  if ! grep -qE '^[[:space:]]*VITE_API_BASE_URL=https?://' "$f"; then
    if grep -qE '^[[:space:]]*VITE_API_BASE_URL=' "$f"; then
      sed -i.bak "s|^[[:space:]]*VITE_API_BASE_URL=.*|${LINE}|" "$f" && rm -f "${f}.bak"
      echo "[ensure-frontend-env] 已修正 ${f} 中的 VITE_API_BASE_URL"
    else
      printf '\n%s\n' "$LINE" >>"$f"
      echo "[ensure-frontend-env] 已追加 VITE_API_BASE_URL 到 ${f}"
    fi
  fi
done
echo "[ensure-frontend-env] 完成。"
