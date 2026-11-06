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


def test_catalog_is_isolated_between_tenants(client):
    token = _admin_token(client)

    tenants = client.get("/api/platform/tenants", headers=_headers(token)).json()["items"]
    flower = next((item for item in tenants if item["slug"] == "flower-shop"), None)
    if not flower:
        created = client.post(
            "/api/platform/tenants",
            headers=_headers(token),
            json={"slug": "flower-shop", "name": "Цветочная лавка"},
        )
        assert created.status_code == 201, created.text
        flower = created.json()

    product = client.post(
        "/api/admin/products",
        headers=_headers(token, host="flower-shop.localhost"),
        json={"title": "Букет пионов", "price": 45, "unit": "piece"},
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]

    public_flower = client.get("/api/products", headers={"host": "flower-shop.localhost"})
    assert public_flower.status_code == 200
    flower_slugs = [item["slug"] for item in public_flower.json()["items"]]
    assert "buket-pionov" in flower_slugs

    public_default = client.get("/api/products", headers={"host": "rybnaya.localhost"})
    assert public_default.status_code == 200
    default_slugs = [item["slug"] for item in public_default.json()["items"]]
    assert "buket-pionov" not in default_slugs

    foreign = client.get(
        f"/api/admin/products/{product_id}",
        headers=_headers(token, host="rybnaya.localhost"),
    )
    assert foreign.status_code == 404

    own = client.get(
        f"/api/admin/products/{product_id}",
        headers=_headers(token, host="flower-shop.localhost"),
    )
    assert own.status_code == 200
    assert own.json()["title"] == "Букет пионов"

    flower_site = client.get("/api/site", headers={"host": "flower-shop.localhost"}).json()
    default_site = client.get("/api/site", headers={"host": "rybnaya.localhost"}).json()
    assert flower_site["settings"]["brand_name"] == "Цветочная лавка"
    assert default_site["settings"]["brand_name"] != "Цветочная лавка"


def _flower_tenant(client):
    token = _admin_token(client)
    tenants = client.get("/api/platform/tenants", headers=_headers(token)).json()["items"]
    flower = next((item for item in tenants if item["slug"] == "flower-shop"), None)
    if not flower:
        response = client.post(
            "/api/platform/tenants",
            headers=_headers(token),
            json={"slug": "flower-shop", "name": "Цветочная лавка", "plan_code": "business"},
        )
        assert response.status_code == 201, response.text
        flower = response.json()
    return token, flower


def test_services_are_visible_and_marked(client):
    token, flower = _flower_tenant(client)
    host = {"host": "flower-shop.localhost"}

    response = client.get("/api/admin/services", headers=_headers(token, **host))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["plan_code"] == "business"
    assert len(data["items"]) >= 40
    by_code = {item["code"]: item for item in data["items"]}
    assert by_code["catalog"]["enabled"] is True
    assert by_code["catalog"]["included_in_plan"] is True
    assert by_code["delivery"]["included_in_plan"] is True
    assert by_code["crm"]["included_in_plan"] is False
    assert by_code["sms_marketing"]["tier"] == "addon"
    assert by_code["sms_marketing"]["price_month"] > 0

    platform_view = client.get(
        f"/api/platform/tenants/{flower['id']}/services", headers=_headers(token)
    )
    assert platform_view.status_code == 200
    assert len(platform_view.json()["items"]) == len(data["items"])


def test_service_dependencies_and_toggle(client):
    token, _flower = _flower_tenant(client)
    host = {"host": "flower-shop.localhost"}

    enabled = client.post(
        "/api/admin/services/delivery/enable", headers=_headers(token, **host)
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True

    blocked = client.post(
        "/api/admin/services/orders/disable", headers=_headers(token, **host)
    )
    assert blocked.status_code == 409
    assert "dependents" in blocked.json()["detail"]

    disabled = client.post(
        "/api/admin/services/delivery/disable", headers=_headers(token, **host)
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False


def test_paid_addon_requires_payment(client):
    token, _flower = _flower_tenant(client)
    host = {"host": "flower-shop.localhost"}

    response = client.post(
        "/api/admin/services/sms_marketing/enable", headers=_headers(token, **host)
    )
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "payment_required"

    services = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    addon = next(item for item in services["items"] if item["code"] == "sms_marketing")
    assert addon["status"] == "pending_payment"


def test_platform_can_lock_and_force_service(client):
    token, flower = _flower_tenant(client)
    host = {"host": "flower-shop.localhost"}

    forced = client.patch(
        f"/api/platform/tenants/{flower['id']}/services/ai_copy",
        headers=_headers(token),
        json={"status": "enabled", "locked_by_platform": True},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["enabled"] is True
    assert forced.json()["locked_by_platform"] is True

    tenant_view = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    ai = next(item for item in tenant_view["items"] if item["code"] == "ai_copy")
    assert ai["enabled"] is True
    assert ai["locked_by_platform"] is True

    blocked = client.post(
        "/api/admin/services/ai_copy/disable", headers=_headers(token, **host)
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "locked_by_platform"


def test_platform_catalog(client):
    token = _admin_token(client)
    response = client.get("/api/platform/catalog", headers=_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert {plan["code"] for plan in data["plans"]} == {"start", "business", "pro"}
    assert len(data["services"]) >= 40
    delivery = next(item for item in data["services"] if item["code"] == "delivery")
    assert delivery["included"]["start"] is False
    assert delivery["included"]["business"] is True
