#!/usr/bin/env bash
# 在仓库根目录构建 user-web / admin-web 并以 local-beta compose 启动（需已配置 .env 文件）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "==> 仓库根目录（脚本已自动 cd 到这里；本机文档路径为 /home/xixiang2025/OM）"
echo "    $ROOT"
echo "    下面带 ==> 的行均为正常步骤提示，不是报错。"

if [[ ! -f backend/.env.local-beta ]]; then
  echo "错误：缺少 backend/.env.local-beta。请执行：cp backend/.env.local-beta.example backend/.env.local-beta 并按说明填写。" >&2
  exit 1
fi
for app in user-web admin-web; do
  if [[ ! -f ${app}/.env.production ]]; then
    echo "错误：缺少 ${app}/.env.production。请执行：cp ${app}/.env.production.example ${app}/.env.production" >&2
    exit 1
  fi
done

echo "==> npm ci && npm run build (user-web)"
( cd user-web && npm ci && npm run build )
echo "==> npm ci && npm run build (admin-web)"
( cd admin-web && npm ci && npm run build )

echo "==> docker compose up -d --build"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml up -d --build

echo "完成。用户站 http://127.0.0.1:8080 ｜ 管理后台 http://127.0.0.1:8081"
echo "上传视频与附件：用户站登录 → 创作；通过后：管理端「视频审核」→ 通过 → 用户站视频列表可见。"
