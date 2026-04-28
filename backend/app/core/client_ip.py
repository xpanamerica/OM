"""从 HTTP 请求解析客户端 IP（限流与审计用，不写入业务表）。"""

from __future__ import annotations

from starlette.requests import Request


def resolved_client_ip(request: Request, *, trust_x_forwarded_for: bool) -> str:
    """若 ``trust_x_forwarded_for``，取 ``X-Forwarded-For`` 最左侧一跳；否则用 ``request.client.host``。"""
    if trust_x_forwarded_for:
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
