#!/usr/bin/env bash
# 检查本机 Docker 守护进程代理 / 基础连通性，便于「起栈前」自检。
# 无需 sudo（读 /etc 若权限不足会跳过并提示）。
set -euo pipefail

echo "=== 1) systemd：docker.service.d/http-proxy.conf（活动 HTTP(S)_PROXY 行）==="
DROP="/etc/systemd/system/docker.service.d/http-proxy.conf"
if [[ -r "${DROP}" ]]; then
  if grep -E '^[[:space:]]*Environment=.*(HTTP|HTTPS)_PROXY' "${DROP}" 2>/dev/null | grep -q .; then
    echo "[WARN] 仍存在未注释的 Environment=HTTP(S)_PROXY，dockerd 会走该代理。"
    echo "       修复：sudo bash $(dirname "$0")/one_shot_fix_docker_all.sh  或  sudo bash $(dirname "$0")/fix_docker_proxy_systemd.sh"
  else
    echo "[OK] 未发现未注释的 HTTP_PROXY/HTTPS_PROXY 行（或文件仅为注释模板）。"
  fi
  echo "--- 文件前 20 行 ---"
  sed -n '1,20p' "${DROP}"
else
  echo "[SKIP] 无法读取 ${DROP}（权限不足或文件不存在）。"
fi

echo
echo "=== 2) docker info 中的代理相关字段（若有）==="
docker info 2>/dev/null | grep -iE 'proxy|http' | head -20 || echo "（无匹配行或无权限执行 docker info）"

echo
echo "=== 3) 用户级 ~/.docker/config.json 中的 proxies（若存在）==="
if [[ -f "${HOME}/.docker/config.json" ]]; then
  grep -n 'proxies\|proxy' "${HOME}/.docker/config.json" 2>/dev/null || echo "（未找到 proxies 字段）"
else
  echo "[OK] 无 ${HOME}/.docker/config.json"
fi

echo
echo "=== 4) 当前 shell 的 HTTP(S)_PROXY（仅影响部分客户端，不等于 dockerd）==="
echo "HTTP_PROXY=${HTTP_PROXY:-<空>}  HTTPS_PROXY=${HTTPS_PROXY:-<空>}"

echo
echo "=== 5) 试拉极小镜像（验证 dockerd 出网；默认走 DaoCloud Hub 代理，避免直连 registry 超时）==="
PROBE_IMAGE="${DOCKER_NETWORK_PROBE_IMAGE:-docker.m.daocloud.io/library/hello-world:latest}"
if docker pull "${PROBE_IMAGE}" 2>&1; then
  echo "[OK] docker pull ${PROBE_IMAGE} 成功。"
else
  echo "[FAIL] docker pull 失败。可设置 DOCKER_NETWORK_PROBE_IMAGE 为可达的测试镜像，或见 docs/runbooks/docker-network-proxy.md。"
  exit 1
fi

echo
echo "=== 6) Compose 拉取本项目 db/redis（使用 compose 内默认镜像与 COMPOSE_HTTP_TIMEOUT）==="
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export COMPOSE_HTTP_TIMEOUT="${COMPOSE_HTTP_TIMEOUT:-300}"
if docker compose pull db redis 2>&1; then
  echo "[OK] docker compose pull db redis 成功。"
else
  echo "[FAIL] compose pull 失败。可检查 .env 中 MEDIA_* 镜像源或网络。"
  exit 1
fi

echo
echo ">>> verify_docker_network_ready：全部通过。可执行：docker compose up -d --build"
