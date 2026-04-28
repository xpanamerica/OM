"""read_compose_first_superuser_password.py 仅依赖脚本路径定位 compose，与进程 cwd 无关。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.docker_bootstrap import backend_root, default_first_superuser_password


def test_extract_matches_subprocess_cli_from_random_cwd(tmp_path: Path):
    script = backend_root() / "scripts" / "read_compose_first_superuser_password.py"
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    from_cli = r.stdout.strip()
    assert from_cli == default_first_superuser_password()


@pytest.mark.skipif(not (backend_root() / "docker-compose.yml").exists(), reason="无 compose")
def test_compose_declares_bootstrap_password_resolvable():
    text = (backend_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "FIRST_SUPERUSER_PASSWORD" in text
    assert "${FIRST_SUPERUSER_PASSWORD:-" in text
    pw = default_first_superuser_password()
    assert len(pw) >= 8
