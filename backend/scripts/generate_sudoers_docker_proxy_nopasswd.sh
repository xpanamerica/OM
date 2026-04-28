#!/usr/bin/env bash
# 生成「仅允许无密码 sudo 执行 fix_docker_proxy_systemd.sh」的 sudoers 片段（写到 stdout）。
# 用法：
#   bash scripts/generate_sudoers_docker_proxy_nopasswd.sh
#   bash scripts/generate_sudoers_docker_proxy_nopasswd.sh | sudo tee /etc/sudoers.d/99-media-channel-docker-proxy-fix >/dev/null
# 更推荐：bash scripts/install_sudoers_docker_proxy_nopasswd.sh（一次输入 sudo 密码）
set -euo pipefail
SCRIPT="$(realpath "$(dirname "${BASH_SOURCE[0]}")/fix_docker_proxy_systemd.sh")"
# sudo 下 id -un 为 root 时，用 SUDO_USER 指向实际登录用户（NOPASSWD 必须写该用户）
if [[ "$(id -un)" == "root" && -n "${SUDO_USER:-}" ]]; then
  USER_NAME="${SUDO_USER}"
else
  USER_NAME="$(id -un)"
fi
# 必须用绝对路径；允许通过 bash 调用以兼容未 chmod +x 的情况
printf '%s ALL=(root) NOPASSWD: /bin/bash %s\n' "${USER_NAME}" "${SCRIPT}"
