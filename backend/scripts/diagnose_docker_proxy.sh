#!/usr/bin/env bash
# 无需 sudo：打印 Docker 与 systemd 代理相关诊断，帮助解释「lookup http」类拉镜像失败。
set -euo pipefail

echo "=== 1) docker pull 试拉（失败时看报错是否含 proxyconnect / lookup http）==="
HTTP_PROXY= HTTPS_PROXY= docker pull hello-world 2>&1 | head -5 || true

echo
echo "=== 2) systemd drop-in（若存在占位或错误 HTTP_PROXY，守护进程会忽略你在 shell 里 unset 的环境变量）==="
DROP="/etc/systemd/system/docker.service.d/http-proxy.conf"
if [[ -f "$DROP" ]]; then
  echo "--- $DROP ---"
  sed -n '1,120p' "$DROP"
else
  echo "未找到 $DROP"
fi

echo
echo "=== 3) 说明 ==="
echo "Linux 上 docker pull / compose 拉镜像通常走 **dockerd 的 Environment**，不是当前 shell 的 HTTP_PROXY。"
echo "若上面文件里仍是 http://your_proxy:your_port/ 等占位，或错误配置，请执行（需 sudo）："
echo "  bash $(dirname "$0")/fix_docker_proxy_systemd.sh"
echo "然后：sudo systemctl daemon-reload && sudo systemctl restart docker"
