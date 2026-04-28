#!/usr/bin/env bash
# 推荐：以仓库根目录打开 Cursor，使用默认集成终端（profile「media_app」已跳过 PhaseAGI 的 ~/.bashrc），
#       再执行本脚本；或在任意终端执行：
#   bash "/home/xixiang2025/OM/backend/scripts/bootstrap_conda_env_media_app.sh"
#
# 作用：创建 conda 环境 media_app（Python 3.11），安装 backend/requirements.txt，
#       并做一次「仅导入」校验与 pytest（需设置 SECRET_KEY / DATABASE_URL，脚本内已设测试用默认值）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "${SCRIPT_DIR}/.." && pwd)"
REQ="${BACKEND}/requirements.txt"

: "${CONDA_BIN:=/home/xixiang2025/software/anaconda3/bin/conda}"
CONDA_ENV_NAME="media_app"

if [[ ! -x "${CONDA_BIN}" ]]; then
  echo "未找到可执行 conda：${CONDA_BIN}。请 export CONDA_BIN=你的路径/bin/conda 后重试。" >&2
  exit 1
fi

if [[ ! -f "${REQ}" ]]; then
  echo "未找到 ${REQ}" >&2
  exit 1
fi

if ! "${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" python -V >/dev/null 2>&1; then
  echo ">>> 创建 Conda 环境：${CONDA_ENV_NAME}（Python 3.11）…"
  "${CONDA_BIN}" create -y -n "${CONDA_ENV_NAME}" python=3.11
else
  echo ">>> 环境 ${CONDA_ENV_NAME} 已存在，跳过 create。"
fi

echo ">>> 升级 pip 并安装项目依赖…"
"${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" python -m pip install -U pip setuptools wheel
"${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" python -m pip install -r "${REQ}"

echo ">>> 校验 FastAPI 应用可导入（不启动 uvicorn、不连库）…"
cd "${BACKEND}"
export SECRET_KEY="${SECRET_KEY:-bootstrap-verify-secret-key-default-48-chars-minimum!!}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@127.0.0.1:5432/videodb}"
"${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" python -c "from app.main import app; print('import_ok', app.title)"

echo ">>> 在 media_app 中跑 pytest（SQLite 内存，与 make test-conda 一致）…"
SECRET_KEY='unit-test-environment-default-secret-48b-min-ok!!' \
  DATABASE_URL='sqlite+pysqlite:///:memory:' \
  REDIS_URL='redis://127.0.0.1:6379/0' \
  "${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" --no-capture-output python -m pytest -q --tb=short

echo ">>> 完成。"
echo "    激活：conda activate ${CONDA_ENV_NAME}"
echo "    测试：cd \"${BACKEND}\" && make test-conda   # 勿依赖被 PhaseAGI 拦截的默认 python"
echo "    启动（需 PostgreSQL/Redis 或 docker compose）："
echo "      cd \"${BACKEND}\" && conda run -n ${CONDA_ENV_NAME} uvicorn app.main:app --host 0.0.0.0 --port 8000"
