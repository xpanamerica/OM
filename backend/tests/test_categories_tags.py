"""阶段 7：分类与标签 API 最小烟测。"""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.repositories import user_repository
from tests.support.openapi_contracts import collect_operation_tags, openapi_skip_unless_exposed


def _admin_headers(db_session, client):
    user_repository.create_user(
        db_session,
        email="cat-admin@example.com",
        username="catadmin",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.ADMIN,
    )
    db_session.commit()
    r = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        data={"username": "catadmin", "password": "secret1234"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_categories_list_public(client):
    p = settings.API_V1_PREFIX
    r = client.get(f"{p}/categories")
    assert r.status_code == 200, r.text
    assert r.json() == []
    cc = (r.headers.get("cache-control") or "").lower()
    assert "private" in cc and "must-revalidate" in cc


def test_category_description_nfkc(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    r = client.post(
        f"{p}/categories",
        headers=hdr,
        json={"name": "nfkc-desc", "description": "  \u3000hello\u3000  "},
    )
    assert r.status_code == 201, r.text
    assert r.json()["description"] == "hello"


def test_tags_list_public(client):
    p = settings.API_V1_PREFIX
    r = client.get(f"{p}/tags")
    assert r.status_code == 200, r.text
    assert r.json() == []
    cc = (r.headers.get("cache-control") or "").lower()
    assert "private" in cc and "must-revalidate" in cc


def test_category_crud_admin_only(client, db_session):
    p = settings.API_V1_PREFIX
    user_repository.create_user(
        db_session,
        email="u1@example.com",
        username="u1",
        hashed_password=get_password_hash("secret1234"),
        role=UserRole.USER,
    )
    db_session.commit()
    login = client.post(
        f"{p}/auth/login",
        data={"username": "u1", "password": "secret1234"},
    )
    user_token = login.json()["access_token"]
    user_hdr = {"Authorization": f"Bearer {user_token}"}

    r_forbidden = client.post(
        f"{p}/categories",
        headers=user_hdr,
        json={"name": "教程", "description": "x"},
    )
    assert r_forbidden.status_code == 403

    hdr = _admin_headers(db_session, client)
    r1 = client.post(
        f"{p}/categories",
        headers=hdr,
        json={"name": " 教程 ", "description": "  入门  "},
    )
    assert r1.status_code == 201, r1.text
    assert "no-store" in (r1.headers.get("cache-control") or "").lower()
    body = r1.json()
    cid = uuid.UUID(body["id"])
    assert body["name"] == "教程"
    assert body["description"] == "入门"

    r_dup = client.post(
        f"{p}/categories",
        headers=hdr,
        json={"name": "教程", "description": None},
    )
    assert r_dup.status_code == 409

    r_list = client.get(f"{p}/categories")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    r_patch = client.patch(
        f"{p}/categories/{cid}",
        headers=hdr,
        json={"description": None},
    )
    assert r_patch.status_code == 200, r_patch.text
    assert "no-store" in (r_patch.headers.get("cache-control") or "").lower()
    assert r_patch.json()["description"] is None

    r_del = client.delete(f"{p}/categories/{cid}", headers=hdr)
    assert r_del.status_code == 204
    assert "no-store" in (r_del.headers.get("cache-control") or "").lower()
    assert client.get(f"{p}/categories").json() == []


def test_tag_update_name_conflict(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    a = client.post(f"{p}/tags", headers=hdr, json={"name": "python"})
    b = client.post(f"{p}/tags", headers=hdr, json={"name": "rust"})
    assert a.status_code == 201 and b.status_code == 201
    bid = uuid.UUID(b.json()["id"])
    r = client.patch(f"{p}/tags/{bid}", headers=hdr, json={"name": "python"})
    assert r.status_code == 409


def test_delete_missing_category_404(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    rid = uuid.uuid4()
    r = client.delete(f"{p}/categories/{rid}", headers=hdr)
    assert r.status_code == 404


def test_category_list_pagination(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    for name in ("a-cat", "b-cat", "c-cat"):
        r = client.post(f"{p}/categories", headers=hdr, json={"name": name, "description": None})
        assert r.status_code == 201, r.text
    r_all = client.get(f"{p}/categories")
    assert len(r_all.json()) == 3
    r_page = client.get(f"{p}/categories", params={"limit": 2, "offset": 0})
    assert r_page.status_code == 200
    assert r_page.headers.get("X-Has-More") == "true"
    assert "X-Next-Cursor" in r_page.headers
    assert [x["name"] for x in r_page.json()] == ["a-cat", "b-cat"]
    r_page2 = client.get(f"{p}/categories", params={"limit": 2, "offset": 2})
    assert r_page2.headers.get("X-Has-More") == "false"
    assert [x["name"] for x in r_page2.json()] == ["c-cat"]


def test_tag_list_keyset_cursor(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    for name in ("ks-a", "ks-b", "ks-c"):
        assert client.post(f"{p}/tags", headers=hdr, json={"name": name}).status_code == 201
    r1 = client.get(f"{p}/tags", params={"limit": 2})
    assert r1.headers.get("X-Has-More") == "true"
    assert "X-Next-Cursor" in r1.headers
    cur = r1.headers["X-Next-Cursor"]
    r2 = client.get(f"{p}/tags", params={"limit": 2, "cursor": cur})
    assert r2.status_code == 200
    assert [x["name"] for x in r2.json()] == ["ks-c"]
    assert r2.headers.get("X-Has-More") == "false"
    assert "X-Next-Cursor" not in r2.headers


def test_cursor_with_offset_mutual_exclusion_400(client):
    p = settings.API_V1_PREFIX
    r = client.get(f"{p}/categories", params={"limit": 5, "offset": 1, "cursor": "e30"})
    assert r.status_code == 400


def test_invalid_cursor_400(client):
    p = settings.API_V1_PREFIX
    r = client.get(f"{p}/tags", params={"limit": 2, "cursor": "not-a-valid-cursor!!!"})
    assert r.status_code == 400


def test_tag_nfkc_collapses_duplicate(client, db_session):
    """NFKC：ﬁ (U+FB01) 与 ASCII fi 归一后视为同名。"""
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    assert client.post(f"{p}/tags", headers=hdr, json={"name": "fix"}).status_code == 201
    r2 = client.post(f"{p}/tags", headers=hdr, json={"name": "\ufb01x"})
    assert r2.status_code == 409


def test_taxonomy_list_invalid_limit_422(client):
    p = settings.API_V1_PREFIX
    r0 = client.get(f"{p}/categories", params={"limit": 0})
    assert r0.status_code == 422
    r501 = client.get(f"{p}/tags", params={"limit": 501})
    assert r501.status_code == 422


def test_list_offset_requires_limit_400(client):
    p = settings.API_V1_PREFIX
    r = client.get(f"{p}/categories", params={"offset": 1})
    assert r.status_code == 400
    assert "limit" in r.json()["detail"]


def test_tag_name_case_insensitive_duplicate(client, db_session):
    p = settings.API_V1_PREFIX
    hdr = _admin_headers(db_session, client)
    assert client.post(f"{p}/tags", headers=hdr, json={"name": "GoLang"}).status_code == 201
    r_dup = client.post(f"{p}/tags", headers=hdr, json={"name": "golang"})
    assert r_dup.status_code == 409


def test_openapi_taxonomy_docs_and_responses(client):
    """Swagger/OpenAPI：中文摘要、401/403/404/409 等说明可被工具读取。"""
    spec = openapi_skip_unless_exposed(client)
    assert {"categories", "tags"} <= collect_operation_tags(spec["paths"])
    prefix = settings.API_V1_PREFIX
    cat_root = spec["paths"][f"{prefix}/categories"]
    assert cat_root["get"]["summary"] == "列出分类"
    assert "公开接口" in (cat_root["get"].get("description") or "")
    get_params = {p["name"] for p in cat_root["get"].get("parameters", [])}
    assert "limit" in get_params and "offset" in get_params and "cursor" in get_params
    get_resp = cat_root["get"].get("responses", {})
    assert "400" in get_resp
    assert "200" in get_resp
    hdrs = get_resp["200"].get("headers", {})
    lower_keys = {k.lower() for k in hdrs}
    assert "x-has-more" in lower_keys
    assert "x-next-cursor" in lower_keys
    assert "cache-control" in lower_keys
    assert cat_root["post"]["summary"] == "创建分类"
    post_resp = cat_root["post"].get("responses", {})
    assert "401" in post_resp and "409" in post_resp
    cat_id_path = next(k for k in spec["paths"] if k.startswith(f"{prefix}/categories/"))
    assert spec["paths"][cat_id_path]["patch"]["summary"] == "更新分类"
    assert "404" in spec["paths"][cat_id_path]["patch"].get("responses", {})

    tag_root = spec["paths"][f"{prefix}/tags"]
    assert tag_root["get"]["summary"] == "列出标签"
    assert "400" in tag_root["get"].get("responses", {})
    assert tag_root["post"]["summary"] == "创建标签"
