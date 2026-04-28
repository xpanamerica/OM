"""HTTP 请求级上下文（与中间件配合，供审计日志等读取）。"""

from __future__ import annotations

import contextvars

request_id_cv: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
