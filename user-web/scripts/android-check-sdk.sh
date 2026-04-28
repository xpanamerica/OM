#!/usr/bin/env bash
# 检查 Android SDK 配置，减少 Android Studio 打开工程后首 Sync 失败。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LP="$ROOT/android/local.properties"

if [[ ! -f "$LP" ]]; then
  echo "未找到 android/local.properties。"
  echo "请任选其一："
  echo "  1) 用 Android Studio 打开 user-web/android，由 IDE 自动生成；或"
  echo "  2) 复制 android/local.properties.example 为 android/local.properties 并填写 sdk.dir="
  exit 1
fi

if ! grep -qE '^sdk\.dir=.+' "$LP" || grep -qE '^sdk\.dir=\s*$' "$LP"; then
  echo "android/local.properties 中 sdk.dir 未填写有效路径。"
  exit 1
fi

echo "✓ 已检测到 android/local.properties 中的 sdk.dir"
