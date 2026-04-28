#!/usr/bin/env python3
"""解析当前环境的首个超级用户明文口令（stdout 一行）。

优先级：
1. ``backend/.env`` 中的 ``FIRST_SUPERUSER_PASSWORD=…``（若存在且非空）
2. 进程环境变量 ``FIRST_SUPERUSER_PASSWORD``
3. ``docker-compose.yml`` 中 ``api.environment`` 的 ``FIRST_SUPERUSER_PASSWORD`` 插值默认段
   ``${FIRST_SUPERUSER_PASSWORD:-…}``（无 .env 覆盖时与容器一致）

供 ``verify_docker_endpoints.sh`` 与测试共用。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _value_from_compose_yaml_field(raw: str) -> str:
    """解析 compose 中 environment 行的右侧（去 YAML 引号，并展开 FIRST_SUPERUSER_PASSWORD 的 :- 默认段）。"""
    s = raw.strip().strip("'\"")
    m = re.fullmatch(r"\$\{FIRST_SUPERUSER_PASSWORD:-(.+)\}", s)
    if m:
        return m.group(1)
    return s


def _from_dotenv(dotenv_path: Path) -> str | None:
    if not dotenv_path.is_file():
        return None
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("FIRST_SUPERUSER_PASSWORD="):
            val = s.split("=", 1)[1].strip().strip('"').strip("'")
            return val or None
    return None


def extract(backend_root: Path | None = None) -> str:
    root = backend_root or Path(__file__).resolve().parent.parent
    dot = _from_dotenv(root / ".env")
    if dot:
        return dot
    env_pw = os.environ.get("FIRST_SUPERUSER_PASSWORD", "").strip()
    if env_pw:
        return env_pw
    compose = root / "docker-compose.yml"
    if not compose.is_file():
        raise FileNotFoundError(f"未找到 {compose}")
    text = compose.read_text(encoding="utf-8")
    m = re.search(r"^\s*FIRST_SUPERUSER_PASSWORD:\s*(.+?)\s*$", text, re.MULTILINE)
    if not m:
        raise ValueError("docker-compose.yml 中未找到 FIRST_SUPERUSER_PASSWORD")
    return _value_from_compose_yaml_field(m.group(1))


def main() -> None:
    try:
        print(extract(), end="")
    except Exception as e:
        print(f"read_compose_first_superuser_password: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
