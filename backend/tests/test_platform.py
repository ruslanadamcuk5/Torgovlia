"""Тесты платформы: арендаторы, домены и определение по Host."""

from app.config import settings


def _admin_token(client) -> str:
    response = client.post(
        "/api/auth/login",
        json={"phone": settings.admin_phone, "password": settings.admin_password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str, **extra: str) -> dict:
    return {"Authorization": f"Bearer {token}", **extra}


def test_site_has_default_tenant(client):
    response = client.get("/api/site")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["tenant"]["slug"] == settings.default_tenant_slug


def test_tenant_resolution_by_host(client):
    response = client.get("/api/site", headers={"host": f"{settings.default_tenant_slug}.localhost"})
    assert response.status_code == 200, response.text
    assert response.json()["tenant"]["slug"] == settings.default_tenant_slug


def test_tenant_header_only_in_development(client):
    response = client.get("/api/site", headers={"x-tenant-slug": settings.default_tenant_slug})
    assert response.status_code == 200
    assert response.json()["tenant"]["slug"] == settings.default_tenant_slug


def test_platform_requires_auth(client):
    response = client.get("/api/platform/tenants")
    assert response.status_code in (401, 403)


def test_platform_tenant_lifecycle(client):
    token = _admin_token(client)

    stats = client.get("/api/platform/stats", headers=_headers(token))
    assert stats.status_code == 200, stats.text
    assert stats.json()["tenants_total"] >= 1

    created = client.post(
        "/api/platform/tenants",
        headers=_headers(token),
        json={
            "slug": "flower-shop",
            "name": "Цветочная лавка",
            "category_preset": "flowers",
            "plan_code": "business",
        },
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["slug"] == "flower-shop"
    assert tenant["status"] == "onboarding"
    assert tenant["domains"][0]["host"] == "flower-shop.localhost"

    duplicate = client.post(
        "/api/platform/tenants",
        headers=_headers(token),
        json={"slug": "flower-shop", "name": "Дубль"},
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/platform/tenants", headers=_headers(token))
    assert listed.status_code == 200
    slugs = [item["slug"] for item in listed.json()["items"]]
    assert "flower-shop" in slugs

    patched = client.patch(
        f"/api/platform/tenants/{tenant['id']}",
        headers=_headers(token),
        json={"status": "active", "name": "Цветы у рынка"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "active"
    assert patched.json()["name"] == "Цветы у рынка"

    site = client.get("/api/site", headers={"host": "flower-shop.localhost"})
    assert site.status_code == 200, site.text
    assert site.json()["tenant"]["slug"] == "flower-shop"
    assert site.json()["tenant"]["plan"] == "business"

    added = client.post(
        f"/api/platform/tenants/{tenant['id']}/domains",
        headers=_headers(token),
        json={"host": "flowers.example.by", "kind": "custom"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["host"] == "flowers.example.by"

    primary = tenant["domains"][0]
    removed = client.delete(
        f"/api/platform/tenants/{tenant['id']}/domains/{primary['id']}",
        headers=_headers(token),
    )
    assert removed.status_code == 409
