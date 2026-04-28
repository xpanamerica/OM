#!/usr/bin/env bash
# 修复 Docker 因 systemd 中无效/占位 HTTP(S)_PROXY 导致无法连接 registry-1.docker.io 的问题。
# 典型报错：proxyconnect tcp: dial tcp: lookup http on ... / no such host
#
# 推荐（安装 NOPASSWD 后无密码）：
#   sudo bash "$(dirname "$0")/fix_docker_proxy_systemd.sh"
# 或首次安装 NOPASSWD：
#   bash scripts/install_sudoers_docker_proxy_nopasswd.sh
#
# 若已是 root（EUID=0），不再嵌套 sudo，便于 sudoers 仅放行「这一条」命令。

set -euo pipefail

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  _as_root() { "$@"; }
else
  _as_root() { sudo "$@"; }
fi

DROP_IN="/etc/systemd/system/docker.service.d/http-proxy.conf"
BACKUP="/etc/systemd/system/docker.service.d/http-proxy.conf.bak.$(date +%Y%m%d%H%M%S)"

if [[ ! -f "${DROP_IN}" ]]; then
  echo "未找到 ${DROP_IN}；若仍无法拉镜像，请检查其他路径的 docker 代理配置或公司网络策略。"
  exit 0
fi

echo ">>> 当前 ${DROP_IN} 内容："
sed -n '1,80p' "${DROP_IN}" || true

if grep -qE 'your_proxy|your_port|example\.com:8080' "${DROP_IN}" 2>/dev/null; then
  echo ">>> 检测到占位/示例代理配置，将禁用（推荐）…"
elif grep -qE '^[[:space:]]*Environment=.*HTTP_PROXY|^[[:space:]]*Environment=.*HTTPS_PROXY' "${DROP_IN}" 2>/dev/null; then
  echo ">>> 检测到 HTTP(S)_PROXY 环境行；将替换为注释模板（禁用代理）。若你使用真实代理，请在脚本执行后手工编辑该文件填入正确 URL。"
else
  echo ">>> 未识别到标准 Environment 行；仍将写入安全模板（仅注释）。可按需自行恢复备份。"
fi

echo ">>> 备份为 ${BACKUP}"
_as_root cp -a "${DROP_IN}" "${BACKUP}"

echo ">>> 写入禁用占位代理的 drop-in（不含有效 Environment= 行）"
_as_root tee "${DROP_IN}" >/dev/null <<'EOF'
# Docker 拉镜像不再使用 systemd 注入的 HTTP(S)_PROXY（此前占位或错误值会导致 registry 连接失败）。
#
# 若需企业代理，取消注释并改为真实地址，然后执行：
#   sudo systemctl daemon-reload && sudo systemctl restart docker
#
# [Service]
# Environment="HTTP_PROXY=http://proxy.example.com:8080/"
# Environment="HTTPS_PROXY=http://proxy.example.com:8080/"
# Environment="NO_PROXY=localhost,127.0.0.1,::1,docker.io,.docker.io"
EOF

echo ">>> 重载 systemd 并重启 docker"
_as_root systemctl daemon-reload
_as_root systemctl restart docker

echo ">>> docker 环境变量（节选）："
_as_root systemctl show docker --property=Environment --no-pager | head -c 2000 || true

echo
echo ">>> 试拉 hello-world（成功表示 registry 可达）"
if docker pull hello-world; then
  echo ">>> 完成：拉镜像已恢复。可在 backend 目录执行：docker compose up -d --build"
elif [[ "${ALLOW_DOCKER_PULL_FAILURE:-}" == "1" ]]; then
  echo ">>> 警告：hello-world 拉取仍失败（ALLOW_DOCKER_PULL_FAILURE=1 已设置，不退出 1）。请检查网络后再 docker pull。"
else
  echo ">>> 仍失败：请检查本机防火墙、公司透明代理、或需配置 registry 镜像加速（daemon.json）。"
  exit 1
fi
