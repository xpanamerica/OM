"""与「容器内 Uvicorn + 默认路由」一致的 HTTP 契约（进程内 TestClient）。

在无法启动 Docker（如 daemon 代理未修复）时，用本文件替代手工 curl 验证：
/docs、/health=200、health JSON 含 database 且 SQLite 下为 connected。
"""

from __future__ import annotations


def test_health_returns_200_and_database_field(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] in ("connected", "disconnected")
    assert body["redis"] in ("connected", "disconnected")
    assert body["status"] in ("ok", "degraded")
    assert body.get("comment_rate_limit_storage") in ("disabled", "redis", "memory")
    assert "comment_rate_limit_use_redis" in body
    assert "comment_rate_limit_redis_fallback_memory" in body
    assert "comment_rate_limit_operational" in body
    assert isinstance(body.get("comment_rate_limit_operational"), bool)
    assert body.get("vod_refresh_rate_limit_storage") in ("disabled", "redis", "memory")
    assert isinstance(body.get("vod_refresh_rate_limit_operational"), bool)
    assert body.get("attachment_post_rate_limit_storage") in ("disabled", "redis", "memory")
    assert isinstance(body.get("attachment_post_rate_limit_operational"), bool)
    # 当前 conftest 使用 SQLite 内存库，SELECT 1 应成功
    assert body["database"] == "connected"


def test_health_propagates_x_request_id(client):
    r = client.get("/health", headers={"X-Request-ID": "probe-req-1"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "probe-req-1"


def test_metrics_not_exposed_by_default(client):
    r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_exposed_when_setting_enabled(client, monkeypatch):
    from app.core.config import settings as s

    monkeypatch.setattr("app.main.settings", s.model_copy(update={"EXPOSE_PROMETHEUS_METRICS": True}))
    from app.infrastructure.observability.comment_metrics import inc_comment_created

    inc_comment_created()
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"app_comments_created_total" in r.content
    assert b"app_view_record_upsert_total" in r.content
    assert b"app_vod_refresh_upload_success_total" in r.content
    assert b"app_upload_flow_metrics_exposition_info" in r.content
    assert b"worker=" in r.content
    assert b"app_comments_metrics_exposition_info" in r.content
    assert b"app_auth_rate_limit_metrics_exposition_info" in r.content


def test_docs_returns_200(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "text/html" in (r.headers.get("content-type") or "")


def test_openapi_returns_200(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "openapi" in data
    assert "paths" in data


def test_unhandled_exception_response_hides_implementation_by_default(client, monkeypatch):
    """默认不向客户端暴露未捕获异常的类型与消息（完整栈仅写服务端日志）。"""
    from app.services import health_service

    def _boom():
        raise RuntimeError("xyzzy-secret-leak-marker")

    monkeypatch.setattr(health_service, "full_health_report", _boom)
    r = client.get("/health")
    assert r.status_code == 500
    payload = r.json()
    assert payload.get("code") == "internal_server_error"
    detail = str(payload.get("detail", ""))
    assert "xyzzy" not in detail
    assert "RuntimeError" not in detail
    assert "服务器内部错误" in detail


def test_unhandled_exception_can_expose_details_when_flag_enabled(client, monkeypatch):
    import app.core.config as cfg
    import app.core.exceptions as ex

    from app.services import health_service

    monkeypatch.setattr(
        ex,
        "settings",
        cfg.settings.model_copy(update={"EXPOSE_INTERNAL_ERROR_DETAILS": True}),
    )

    def _boom():
        raise RuntimeError("visible-for-local-debug")

    monkeypatch.setattr(health_service, "full_health_report", _boom)
    r = client.get("/health")
    assert r.status_code == 500
    assert "visible-for-local-debug" in str(r.json().get("detail", ""))
