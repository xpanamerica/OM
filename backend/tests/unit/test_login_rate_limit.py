from __future__ import annotations

from starlette.datastructures import Headers
from starlette.requests import Request

from app.core.client_ip import resolved_client_ip
from app.core.login_rate_limit import is_login_allowed


def test_is_login_allowed_respects_threshold():
    ip = "192.0.2.77"
    assert is_login_allowed(ip, max_attempts_per_minute=3) is True
    assert is_login_allowed(ip, max_attempts_per_minute=3) is True
    assert is_login_allowed(ip, max_attempts_per_minute=3) is True
    assert is_login_allowed(ip, max_attempts_per_minute=3) is False
    assert is_login_allowed("192.0.2.78", max_attempts_per_minute=3) is True


def test_is_login_allowed_zero_means_unlimited():
    assert is_login_allowed("192.0.2.99", max_attempts_per_minute=0) is True
    assert is_login_allowed("192.0.2.99", max_attempts_per_minute=0) is True


def test_resolved_client_ip_xff_optional():
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
        "client": ("10.0.0.2", 12345),
    }
    req = Request(scope)
    assert resolved_client_ip(req, trust_x_forwarded_for=True) == "203.0.113.10"
    assert resolved_client_ip(req, trust_x_forwarded_for=False) == "10.0.0.2"
