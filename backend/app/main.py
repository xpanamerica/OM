from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.http_middleware import AccessLogMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware
from app.core.logging import setup_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.infrastructure.idempotency_store import verify_idempotency_startup
from app.infrastructure.observability.metrics import setup_metrics
from app.infrastructure.observability.tracing import setup_tracing
from app.services import health_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    verify_idempotency_startup()
    setup_metrics()
    setup_tracing()
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


_docs = "/docs" if settings.expose_openapi_docs else None
_redoc = "/redoc" if settings.expose_openapi_docs else None
_openapi = "/openapi.json" if settings.expose_openapi_docs else None

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
)
_origins = settings.CORS_ORIGINS
# 规范：Access-Control-Allow-Origin=* 时不得与 credentials 同时为 true
_allow_credentials = "*" not in _origins
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
# 压缩 JSON/HTML 等文本响应，降低带宽与首包时间（客户端须带 Accept-Encoding: gzip）
app.add_middleware(GZipMiddleware, minimum_size=1000)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Prometheus textformat（评论 + 播放记录 + 上传链路等进程内计数器）；默认关闭，见 ``EXPOSE_PROMETHEUS_METRICS``。"""
    if not settings.EXPOSE_PROMETHEUS_METRICS:
        return Response(status_code=404)
    from app.infrastructure.observability.comment_metrics import render_comment_metrics_prometheus_text
    from app.infrastructure.observability.upload_flow_metrics import render_upload_flow_metrics_prometheus_text
    from app.infrastructure.observability.view_record_metrics import render_view_record_metrics_prometheus_text

    body = (
        render_comment_metrics_prometheus_text()
        + render_view_record_metrics_prometheus_text()
        + render_upload_flow_metrics_prometheus_text()
    )
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/health")
def health():
    """与后续 `GET /api/v1/admin/health` 共用 `full_health_report` 字段口径。"""
    return JSONResponse(
        content=health_service.full_health_report(),
        headers={"Cache-Control": "no-store, max-age=0"},
    )
