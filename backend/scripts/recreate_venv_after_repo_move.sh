#!/usr/bin/env bash
# 仓库根目录改名或移动后，backend/.venv 内 shebang 仍指向旧路径，需重建。
# 用法（在任意目录）：bash backend/scripts/recreate_venv_after_repo_move.sh
# 或：cd backend && bash scripts/recreate_venv_after_repo_move.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND}"

PY="${PYTHON:-python3}"
if ! "${PY}" -m venv --help >/dev/null 2>&1; then
  echo "未找到可用的 ${PY}，请安装 Python 3 或设置 PYTHON=/path/to/python3" >&2
  exit 1
fi

echo ">>> 删除旧 .venv（若存在）…"
rm -rf .venv

echo ">>> 创建新 .venv …"
"${PY}" -m venv .venv

# shellcheck disable=SC1091
. .venv/bin/activate

echo ">>> 安装依赖 …"
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt

echo ">>> 完成：${BACKEND}/.venv"
python -c "import sys; print('python:', sys.executable)"
