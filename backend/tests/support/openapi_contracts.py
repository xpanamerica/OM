"""OpenAPI 契约辅助：多阶段 HTTP 测试共用，避免重复收集 paths/tags。"""

from __future__ import annotations

from typing import Any

import pytest


def openapi_skip_unless_exposed(client: Any) -> dict[str, Any]:
    """未暴露 ``/openapi.json`` 时 ``pytest.skip``，否则返回解析后的 spec。"""
    r = client.get("/openapi.json")
    if r.status_code != 200:
        pytest.skip("当前环境未暴露 OpenAPI（见 ``expose_openapi_docs``）")
    return r.json()


def collect_operation_tags(paths: dict[str, Any]) -> set[str]:
    """从 OpenAPI ``paths`` 下各 method 收集所有 operation ``tags``。"""
    tags: set[str] = set()
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if isinstance(op, dict) and "tags" in op:
                tags.update(op["tags"])
    return tags


def assert_openapi_paths(paths: dict[str, Any], *expected_keys: str) -> None:
    """断言给定 path key（含 ``{param}`` 占位）均存在于 spec。"""
    missing = [k for k in expected_keys if k not in paths]
    assert not missing, f"OpenAPI paths 缺少: {missing}；示例: {list(paths)[:16]}"
