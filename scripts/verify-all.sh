#!/usr/bin/env bash
# 从仓库根目录一键跑通 user-web / admin-web / backend 单元与构建（避免在子目录里 cd 失败）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/user-web"
npm install --no-audit --no-fund
npm run test
npm run typecheck
npm run build
# Capacitor：与上架壳一致须相对 base；若未初始化 android/ 目录则跳过
if [[ -d "$ROOT/user-web/android" ]]; then
  npm run build:cap
  npm run cap:sync
fi
cd "$ROOT/admin-web"
npm install --no-audit --no-fund
npm run test
npm run typecheck
npm run build
cd "$ROOT/backend"
if [[ -x .venv/bin/pytest ]]; then
  .venv/bin/pytest tests/unit/ -q
else
  echo "跳过 backend：未找到 .venv/bin/pytest（请先 cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt）" >&2
  exit 1
fi
echo "verify-all: OK"
