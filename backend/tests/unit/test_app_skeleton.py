def test_import_app():
    from app.main import app

    assert app.title


def test_openapi_gzip_when_client_accepts_encoding(client):
    """GZipMiddleware：较大 JSON 在 Accept-Encoding: gzip 时应压缩（降低传输体积）。"""
    r = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert len(r.content) > 200
    assert r.headers.get("content-encoding", "").lower() == "gzip"


def test_health_and_openapi(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("connected", "disconnected")
    assert body["redis"] in ("connected", "disconnected")
    assert body.get("comment_rate_limit_storage") in ("disabled", "redis", "memory")
    assert "comment_rate_limit_use_redis" in body
    assert "comment_rate_limit_redis_fallback_memory" in body
    assert "comment_rate_limit_operational" in body
    assert body.get("vod_refresh_rate_limit_storage") in ("disabled", "redis", "memory")
    assert "vod_refresh_rate_limit_operational" in body
    assert body.get("attachment_post_rate_limit_storage") in ("disabled", "redis", "memory")
    assert "attachment_post_rate_limit_operational" in body

    r2 = client.get("/openapi.json")
    assert r2.status_code == 200
    assert "paths" in r2.json()
