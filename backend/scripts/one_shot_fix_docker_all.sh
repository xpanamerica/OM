#!/usr/bin/env bash
# 一条 sudo 会话内完成：
#   1) 安装 NOPASSWD sudoers（以后无需再为修复脚本输密码）
#   2) 清空无效 systemd Docker 代理、重启 dockerd、试拉 hello-world
#
# 用法（复制整行到系统终端，**只提示一次** sudo 密码）：
#   sudo bash "$(realpath scripts/one_shot_fix_docker_all.sh)"
#
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请在本机终端执行下面**一整行**（会提示一次 sudo 密码）："
  echo
  echo "sudo bash $(realpath "${BASH_SOURCE[0]}")"
  echo
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -z "${SUDO_USER:-}" || "${SUDO_USER}" == "root" ]]; then
  echo "错误：未设置 SUDO_USER。请使用「sudo bash $(basename "${BASH_SOURCE[0]}")」，不要用「sudo -i」后再执行。"
  exit 1
fi

export SUDO_USER

echo ">>> [1/2] 安装 NOPASSWD sudoers（用户: ${SUDO_USER}）…"
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
bash "${SCRIPT_DIR}/generate_sudoers_docker_proxy_nopasswd.sh" >"${TMP}"
cat "${TMP}"
install -m 0440 "${TMP}" /etc/sudoers.d/99-media-channel-docker-proxy-fix
visudo -c -f /etc/sudoers.d/99-media-channel-docker-proxy-fix

echo ">>> [2/2] 修复 Docker systemd 代理并重启（允许拉取失败时仍完成其余步骤）…"
ALLOW_DOCKER_PULL_FAILURE=1 bash "${SCRIPT_DIR}/fix_docker_proxy_systemd.sh"

FIX="$(realpath "${SCRIPT_DIR}/fix_docker_proxy_systemd.sh")"
echo
echo ">>> 基础修复已完成。"
echo "    若 hello-world 曾失败，请检查网络后执行：docker pull hello-world"
echo "    再次仅修复代理/重启（已免密）：sudo -n bash ${FIX}"
echo "    启动项目：cd ${BACKEND} && docker compose up -d --build"
