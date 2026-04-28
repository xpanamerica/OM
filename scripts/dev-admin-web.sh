#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${ROOT}/scripts/ensure-frontend-env.sh"
cd "${ROOT}/admin-web"
exec npm run dev
