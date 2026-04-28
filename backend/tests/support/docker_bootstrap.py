"""从 docker-compose.yml 读取默认引导配置（委托 scripts 下单一解析脚本，避免重复正则）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_first_superuser_password() -> str:
    script = backend_root() / "scripts" / "read_compose_first_superuser_password.py"
    spec = importlib.util.spec_from_file_location("_compose_superuser_pw", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    extract = getattr(mod, "extract", None)
    if extract is None:
        raise RuntimeError("read_compose_first_superuser_password 缺少 extract()")
    return extract(backend_root())
