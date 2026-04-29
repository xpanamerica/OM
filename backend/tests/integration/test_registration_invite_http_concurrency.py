"""真实 HTTP 进程级并发：一次性邀请码只能有一个注册请求成功。

本用例不使用 ``TestClient`` 多线程；它启动独立 Uvicorn 子进程，并用
``httpx`` 同时提交多个注册请求。默认使用临时 SQLite 文件库；CI 可通过
``INVITE_HTTP_CONCURRENCY_DATABASE_URL`` 切到 PostgreSQL，验证生产同类数据库语义。
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - 注册 metadata
from app.db.base import Base
from app.models.invite_code import InviteCode
from app.repositories import app_setting_repository, invite_code_repository

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INVITE_HTTP_CONCURRENCY", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_INVITE_HTTP_CONCURRENCY=1 to run the real Uvicorn/httpx invite race test.",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _database_url(tmp_path: Path) -> tuple[str, bool]:
    external = (os.environ.get("INVITE_HTTP_CONCURRENCY_DATABASE_URL") or "").strip()
    if external:
        return external, False
    db_file = tmp_path / "invite_http_concurrency.sqlite3"
    return f"sqlite+pysqlite:///{db_file}", True


async def _wait_until_healthy(base_url: str) -> None:
    deadline = time.monotonic() + 20
    async with httpx.AsyncClient(timeout=1.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(f"{base_url}/health")
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.15)
    raise AssertionError("Uvicorn test server did not become healthy in time")


async def _post_register(base_url: str, idx: int, invite_code: str, suffix: str) -> int:
    # 首次注册会做 bcrypt；CI 小机器并发时需要留足时间，避免把性能波动误判为并发语义失败。
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{base_url}/api/v1/auth/register",
            json={
                "email": f"race{suffix.lower()}{idx}@example.com",
                "username": f"race{suffix.lower()}{idx}",
                "password": "secret1234",
                "invite_code": invite_code,
            },
        )
        return r.status_code


async def _race_registers(base_url: str, invite_code: str, suffix: str) -> list[int]:
    return await asyncio.gather(*[_post_register(base_url, i, invite_code, suffix) for i in range(4)])


def test_http_concurrent_one_time_invite_only_one_201(tmp_path: Path):
    db_url, should_create_schema = _database_url(tmp_path)
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
    if should_create_schema:
        Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    suffix = uuid.uuid4().hex[:12].upper()
    with SessionLocal() as db:
        app_setting_repository.set_value(
            db,
            key="registration_invite_code_required",
            value="true",
        )
        row = invite_code_repository.create_invite(
            db,
            code=f"HTTPRACE{suffix}",
            created_by=None,
            expires_at=None,
            max_uses=1,
        )
        db.commit()
        invite_code = row.code

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "SECRET_KEY": "unit-test-environment-default-secret-48b-min-ok!!",
            "DATABASE_URL": db_url,
            "REDIS_URL": "redis://127.0.0.1:6379/15",
            "AUTH_RATE_LIMIT_ENABLED": "false",
            "AUTH_RATE_LIMIT_USE_REDIS": "false",
            "AUTH_REGISTRATION_REQUIRES_APPROVAL": "false",
            "LOG_LEVEL": "WARNING",
        }
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        asyncio.run(_wait_until_healthy(base_url))
        statuses = asyncio.run(_race_registers(base_url, invite_code, suffix))
    finally:
        try:
            proc.terminate()
        except PermissionError:
            # Cursor sandbox can deny SIGTERM to child processes; normal CI/Linux runners allow it.
            pass
        try:
            proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.communicate(timeout=8)
            except PermissionError:
                pass

    assert statuses.count(201) == 1, statuses
    assert all(s in {201, 400, 409} for s in statuses), statuses

    with SessionLocal() as db:
        inv = db.scalars(select(InviteCode).where(InviteCode.code == invite_code)).one()
        assert inv.used_count == 1
        assert inv.status == "used"
        assert inv.used_by is not None
