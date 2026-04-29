#!/usr/bin/env bash
# 将历史目录「~/媒体频道」指向当前仓库 OM，避免 Docker 仍绑定旧路径时挂载到空目录。
# 用法（在任意目录执行即可）：
#   bash /home/xixiang2025/OM/backend/scripts/fix_legacy_media_channel_symlink.sh
set -euo pipefail

OM_REAL="${OM_REAL:-$HOME/OM}"
OLD_MEDIA="$HOME/媒体频道"

if [[ ! -d "$OM_REAL" ]]; then
  echo "错误：未找到 OM 仓库目录：$OM_REAL" >&2
  echo "可设置环境变量后重试，例如：OM_REAL=/path/to/OM bash $0" >&2
  exit 1
fi

if [[ -L "$OLD_MEDIA" ]]; then
  cur="$(readlink -f "$OLD_MEDIA" 2>/dev/null || true)"
  if [[ "$cur" == "$(readlink -f "$OM_REAL")" ]]; then
    echo "已存在正确符号链接：$OLD_MEDIA -> $OM_REAL"
    exit 0
  fi
  echo "替换已有符号链接：$OLD_MEDIA -> $OM_REAL"
  rm -f "$OLD_MEDIA"
elif [[ -d "$OLD_MEDIA" ]]; then
  echo "发现旧路径目录（可能为空或过时）：$OLD_MEDIA"
  echo "将删除后改为指向 $OM_REAL 的符号链接（若为 root 所有需输入 sudo 密码）"
  sudo rm -rf "$OLD_MEDIA"
fi

ln -sfn "$OM_REAL" "$OLD_MEDIA"
echo "已创建：$OLD_MEDIA -> $OM_REAL"
echo "此后 $OLD_MEDIA/backend 即 $OM_REAL/backend（含 alembic.ini）。"
echo "请重建仍挂载旧路径的 API 容器，例如："
echo "  cd $OM_REAL/backend && docker compose -p backend up -d --force-recreate api"
