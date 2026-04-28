"""以 docker-compose.yml 为权威：口令解析脚本、.env.example、文档与 compose 一致。"""

from __future__ import annotations

import re

import pytest

from tests.support.docker_bootstrap import backend_root, default_first_superuser_password

COMPOSE = backend_root() / "docker-compose.yml"
VERIFY_SCRIPT = backend_root() / "scripts" / "verify_docker_endpoints.sh"
READ_SCRIPT = backend_root() / "scripts" / "read_compose_first_superuser_password.py"
ENV_EXAMPLE = backend_root() / ".env.example"
CREATE_SUPERUSER_DOC = backend_root() / "scripts" / "create_superuser.md"


@pytest.mark.skipif(not COMPOSE.exists(), reason="无 docker-compose.yml")
def test_default_superuser_password_synced_across_repo():
    pw = default_first_superuser_password()
    assert len(pw) >= 8
    assert len(pw.encode("utf-8")) <= 72, "compose 默认口令须在 bcrypt UTF-8 72 字节限制内"

    verify_txt = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert "read_compose_first_superuser_password.py" in verify_txt, (
        "verify_docker_endpoints.sh 应调用 read_compose_first_superuser_password.py 解析 compose"
    )

    env_txt = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "FIRST_SUPERUSER" in env_txt, ".env.example 应提示 FIRST_SUPERUSER_* 变量（注释或说明）"
    assert not re.search(
        rf"^FIRST_SUPERUSER_PASSWORD={re.escape(pw)}\s*$",
        env_txt,
        re.MULTILINE,
    ), ".env.example 不得写入与 compose 相同的默认首管口令（口令仅保留在 compose 内联默认与文档 curl 示例）"

    doc = CREATE_SUPERUSER_DOC.read_text(encoding="utf-8")
    assert "read_compose_first_superuser_password.py" in doc, "create_superuser.md 应说明通过解析脚本获取当前首管口令"

    assert READ_SCRIPT.is_file(), "scripts/read_compose_first_superuser_password.py 须存在"
