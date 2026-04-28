"""用户模块放行清单（与产品验收一一对应）。

运行：``pytest tests/test_user_module_completion_gate.py -v``

对应关系：
  • 服务能启动 — ``test_gate_01_application_imports``
  • migration 成功 — ``test_gate_02_alembic_upgrade_head_sqlite_file``
  • /docs 正常 — ``test_gate_03_openapi_docs_available``
  • 注册 / 登录 /me / 非法 token / 重复注册 / 非明文密码 — ``test_gate_04_auth_security_acceptance``

说明：CI 与 ``conftest`` 将 ``AUTH_LOGIN_MAX_ATTEMPTS_PER_MINUTE=0`` 关闭登录限流，避免与其它用例争抢同一客户端 IP 计数。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_gate_01_application_imports():
    """服务能启动：应用对象可被加载（等价于 Uvicorn 可挂载）。"""
    assert app is not None
    assert app.title


def test_gate_02_alembic_upgrade_head_sqlite_file(tmp_path):
    """migration 成功：在临时 SQLite 文件上 ``alembic upgrade head`` 退出码 0。"""
    db_file = tmp_path / "user_module_gate.db"
    database_url = "sqlite:///" + db_file.resolve().as_posix()
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["SECRET_KEY"] = "a" * 48
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"alembic upgrade head 失败:\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def test_gate_03_openapi_docs_available(client):
    """/docs（及 OpenAPI JSON）在默认 local 环境下可访问。"""
    r = client.get("/docs")
    assert r.status_code == 200, "/docs 须 200"
    assert "html" in (r.headers.get("content-type") or "").lower()
    r2 = client.get("/openapi.json")
    assert r2.status_code == 200, "/openapi.json 须 200"
    assert "openapi" in r2.json()


def test_gate_04_auth_security_acceptance(client, db_session):
    """注册、登录、/me、非法 token、重复注册、口令非明文。"""
    p = settings.API_V1_PREFIX
    reg = {"email": "gate_user@example.com", "username": "gateuser", "password": "gatePass1234"}

    r = client.post(f"{p}/auth/register", json=reg)
    assert r.status_code == 201, f"注册须成功: {r.status_code} {r.text}"

    r = client.post(
        f"{p}/auth/login",
        data={"username": "gateuser", "password": "gatePass1234"},
    )
    assert r.status_code == 200, f"登录须成功: {r.status_code} {r.text}"
    token = r.json()["access_token"]

    r = client.get(f"{p}/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"/me 须成功: {r.status_code} {r.text}"
    assert r.json()["username"] == "gateuser"

    r = client.get(
        f"{p}/users/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.e30"},
    )
    assert r.status_code == 401, "非法 token 须 401"

    r = client.post(f"{p}/auth/register", json=reg)
    assert r.status_code == 409, f"重复注册（同邮箱）须 409: {r.status_code} {r.text}"

    r = client.post(
        f"{p}/auth/register",
        json={
            "email": "gate_user2@example.com",
            "username": "gateuser",
            "password": "gatePass1234",
        },
    )
    assert r.status_code == 409, f"重复注册（同用户名）须 409: {r.status_code} {r.text}"

    row = db_session.execute(select(User).where(User.email == "gate_user@example.com")).scalar_one()
    hp = row.hashed_password
    assert hp.startswith("$2"), "口令须以 bcrypt 哈希存储"
    assert reg["password"] not in hp, "库中不得含明文口令"
