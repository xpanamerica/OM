"""SecurityHeadersMiddleware 与 gzip 等 HTTP 面回归（通过临时替换中间件模块内 settings）。"""

import pytest

from app.core import config


@pytest.fixture
def _strict_http_settings(monkeypatch):
    """与生产类似：不暴露 OpenAPI，从而启用安全响应头。"""
    from app.core import http_middleware as mw

    s = config.settings.model_copy(update={"EXPOSE_OPENAPI_DOCS": False})
    monkeypatch.setattr(mw, "settings", s)
    yield s


def test_health_always_includes_baseline_security_headers(client):
    """即使暴露 OpenAPI（开发默认），也应带上 nosniff + Referrer-Policy。"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_security_headers_on_health_when_openapi_suppressed(client, _strict_http_settings):
    r = client.get("/health")
    assert r.status_code == 200
    assert "no-store" in (r.headers.get("cache-control") or "").lower()
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    pp = r.headers.get("permissions-policy") or ""
    assert "geolocation=()" in pp


def test_strict_transport_security_when_configured(client, monkeypatch):
    from app.core import http_middleware as mw

    s = config.settings.model_copy(update={"EXPOSE_OPENAPI_DOCS": False, "SECURITY_HSTS_MAX_AGE": 60})
    monkeypatch.setattr(mw, "settings", s)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("strict-transport-security") == "max-age=60"


def test_security_headers_with_request_id_middleware(client, _strict_http_settings):
    """安全头与 RequestId 等其它中间件同栈时不互相覆盖。"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")
    assert r.headers.get("x-content-type-options") == "nosniff"
