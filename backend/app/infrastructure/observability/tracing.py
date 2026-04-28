"""OpenTelemetry 追踪占位。

生产接入建议：
- FastAPI 使用 OTel ASGI 中间件
- SQLAlchemy 使用对应 instrumentation
"""


def setup_tracing() -> None:
    """预留：配置 TracerProvider、Exporter。"""
    return None
