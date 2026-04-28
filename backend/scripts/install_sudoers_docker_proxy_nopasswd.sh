#!/usr/bin/env bash
# 安装极窄 NOPASSWD sudoers：之后可无密码执行
#   sudo -n bash "$(realpath scripts/fix_docker_proxy_systemd.sh)"
#
# 行为：
# - 若已是 root / 或 `sudo -n` 可用：直接写入 /etc/sudoers.d/
# - 若在交互终端：用 `sudo` 提示一次密码后写入
# - 若在非交互环境（如 Cursor Agent）：把规则写入 backend/.cache/sudoers/ 并打印**一条**可复制命令，你在系统终端粘贴执行一次即可

set -euo pipefail
# 仓库 backend/ 根目录（本文件在 backend/scripts/ 下）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${ROOT}/.cache/sudoers"
CACHE_FILE="${CACHE_DIR}/99-media-channel-docker-proxy-fix"
TARGET="/etc/sudoers.d/99-media-channel-docker-proxy-fix"

mkdir -p "${CACHE_DIR}"
bash "${ROOT}/scripts/generate_sudoers_docker_proxy_nopasswd.sh" >"${CACHE_FILE}"
chmod 600 "${CACHE_FILE}"

echo ">>> NOPASSWD 规则内容："
cat "${CACHE_FILE}"
echo ">>> 已写入本仓库（便于复制）：${CACHE_FILE}"

install_to_etc() {
  local src="$1"
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    install -m 0440 "${src}" "${TARGET}"
    visudo -c -f "${TARGET}"
  else
    sudo install -m 0440 "${src}" "${TARGET}"
    sudo visudo -c -f "${TARGET}"
  fi
}

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo ">>> 当前为 root，直接安装到 ${TARGET}"
  install_to_etc "${CACHE_FILE}"
elif sudo -n true 2>/dev/null; then
  echo ">>> 检测到 sudo 免密，直接安装到 ${TARGET}"
  install_to_etc "${CACHE_FILE}"
elif [[ -t 0 ]]; then
  echo ">>> 交互式终端：将提示一次 sudo 密码…"
  sudo install -m 0440 "${CACHE_FILE}" "${TARGET}"
  sudo visudo -c -f "${TARGET}"
else
  echo
  echo ">>> 非交互环境无法输入 sudo 密码。请在系统终端执行下面**一整行**（仅一次密码）："
  echo
  echo "sudo install -m 440 '${CACHE_FILE}' '${TARGET}' && sudo visudo -c -f '${TARGET}'"
  echo
  echo ">>> 安装完成后验证（应无密码提示）："
  echo "sudo -n bash $(realpath "${ROOT}/scripts/fix_docker_proxy_systemd.sh")"
  exit 0
fi

FIX="$(realpath "${ROOT}/scripts/fix_docker_proxy_systemd.sh")"
echo ">>> 完成。验证（不应再提示密码）："
echo "    sudo -n bash ${FIX}"
