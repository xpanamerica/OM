#!/usr/bin/env bash
# 在 macOS 上安装 iOS 依赖，避免直接双击 .xcodeproj 导致 Pods 缺失。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/ios/App"

if ! command -v pod >/dev/null 2>&1; then
  echo "未找到 pod。请先安装 CocoaPods，例如：brew install cocoapods" >&2
  exit 1
fi

pod install
echo ""
echo "✓ Pod 安装完成。请用 Xcode 打开："
echo "  $ROOT/ios/App/App.xcworkspace"
echo "（务必打开 .xcworkspace，不要单独打开 .xcodeproj）"
