"""Тесты платформы: арендаторы, домены, сервисы и изоляция магазинов."""

from app.config import settings


FLOWER_PHONE = "+375291112288"
FLOWER_PASSWORD = "Flower123!"
FLOWER_HOST = "flower-shop.localhost"


def _platform_token(client) -> str:
    response = client.post(
        "/api/platform/auth/login",
        json={
            "phone": settings.platform_admin_phone,
            "password": settings.platform_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token(client, host: str | None = None) -> str:
    headers = {"host": host} if host else {}
    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={"phone": settings.admin_phone, "password": settings.admin_password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _tenant_token(client, phone: str, password: str, host: str) -> str:
    response = client.post(
        "/api/auth/login",
        headers={"host": host},
        json={"phone": phone, "password": password},
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


def test_tenant_admin_cannot_open_platform(client):
    token = _admin_token(client)
    response = client.get("/api/platform/tenants", headers=_headers(token))
    assert response.status_code == 401


def test_platform_tenant_lifecycle(client):
    token = _platform_token(client)

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
            "owner_phone": FLOWER_PHONE,
            "owner_name": "Владелец цветочной лавки",
            "owner_password": FLOWER_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["slug"] == "flower-shop"
    assert tenant["status"] == "onboarding"
    assert tenant["domains"][0]["host"] == FLOWER_HOST

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

    site = client.get("/api/site", headers={"host": FLOWER_HOST})
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


def test_tenant_tokens_do_not_cross_stores(client):
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    response = client.get(
        "/api/admin/products",
        headers=_headers(flower_token, host=f"{settings.default_tenant_slug}.localhost"),
    )
    assert response.status_code == 401


def test_catalog_is_isolated_between_tenants(client):
    platform_token = _platform_token(client)
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    default_token = _admin_token(client, host=f"{settings.default_tenant_slug}.localhost")

    tenants = client.get(
        "/api/platform/tenants", headers=_headers(platform_token)
    ).json()["items"]
    flower = next(item for item in tenants if item["slug"] == "flower-shop")

    product = client.post(
        "/api/admin/products",
        headers=_headers(flower_token, host=FLOWER_HOST),
        json={"title": "Букет пионов", "price": 45, "unit": "piece"},
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]

    public_flower = client.get("/api/products", headers={"host": FLOWER_HOST})
    assert public_flower.status_code == 200
    flower_slugs = [item["slug"] for item in public_flower.json()["items"]]
    assert "buket-pionov" in flower_slugs

    public_default = client.get(
        "/api/products", headers={"host": f"{settings.default_tenant_slug}.localhost"}
    )
    assert public_default.status_code == 200
    default_slugs = [item["slug"] for item in public_default.json()["items"]]
    assert "buket-pionov" not in default_slugs

    foreign = client.get(
        f"/api/admin/products/{product_id}",
        headers=_headers(default_token, host=f"{settings.default_tenant_slug}.localhost"),
    )
    assert foreign.status_code == 404

    own = client.get(
        f"/api/admin/products/{product_id}",
        headers=_headers(flower_token, host=FLOWER_HOST),
    )
    assert own.status_code == 200
    assert own.json()["title"] == "Букет пионов"

    flower_site = client.get("/api/site", headers={"host": FLOWER_HOST}).json()
    default_site = client.get(
        "/api/site", headers={"host": f"{settings.default_tenant_slug}.localhost"}
    ).json()
    assert flower_site["settings"]["brand_name"] == "Цветочная лавка"
    assert default_site["settings"]["brand_name"] != "Цветочная лавка"

    # Тот же телефон может быть покупателем в другом магазине.
    same_phone = client.post(
        "/api/admin/users",
        headers=_headers(default_token, host=f"{settings.default_tenant_slug}.localhost"),
        json={
            "phone": FLOWER_PHONE,
            "full_name": "Покупатель в рыбном",
            "password": "Customer123!",
            "role": "customer",
        },
    )
    assert same_phone.status_code in (200, 201), same_phone.text


def _flower_ids(client):
    platform_token = _platform_token(client)
    tenants = client.get(
        "/api/platform/tenants", headers=_headers(platform_token)
    ).json()["items"]
    flower = next(item for item in tenants if item["slug"] == "flower-shop")
    return platform_token, flower


def test_services_are_visible_and_marked(client):
    platform_token, flower = _flower_ids(client)
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    host = {"host": FLOWER_HOST}

    response = client.get("/api/admin/services", headers=_headers(flower_token, **host))
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
        f"/api/platform/tenants/{flower['id']}/services", headers=_headers(platform_token)
    )
    assert platform_view.status_code == 200
    assert len(platform_view.json()["items"]) == len(data["items"])


def test_service_dependencies_and_toggle(client):
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    host = {"host": FLOWER_HOST}

    enabled = client.post(
        "/api/admin/services/delivery/enable", headers=_headers(flower_token, **host)
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True

    blocked = client.post(
        "/api/admin/services/orders/disable", headers=_headers(flower_token, **host)
    )
    assert blocked.status_code == 409
    assert "dependents" in blocked.json()["detail"]

    disabled = client.post(
        "/api/admin/services/delivery/disable", headers=_headers(flower_token, **host)
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False


def test_paid_addon_requires_payment(client):
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    host = {"host": FLOWER_HOST}

    response = client.post(
        "/api/admin/services/sms_marketing/enable", headers=_headers(flower_token, **host)
    )
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "payment_required"

    services = client.get("/api/admin/services", headers=_headers(flower_token, **host)).json()
    addon = next(item for item in services["items"] if item["code"] == "sms_marketing")
    assert addon["status"] == "pending_payment"


def test_platform_can_lock_and_force_service(client):
    platform_token, flower = _flower_ids(client)
    flower_token = _tenant_token(client, FLOWER_PHONE, FLOWER_PASSWORD, FLOWER_HOST)
    host = {"host": FLOWER_HOST}

    forced = client.patch(
        f"/api/platform/tenants/{flower['id']}/services/ai_copy",
        headers=_headers(platform_token),
        json={"status": "enabled", "locked_by_platform": True},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["enabled"] is True
    assert forced.json()["locked_by_platform"] is True

    tenant_view = client.get(
        "/api/admin/services", headers=_headers(flower_token, **host)
    ).json()
    ai = next(item for item in tenant_view["items"] if item["code"] == "ai_copy")
    assert ai["enabled"] is True
    assert ai["locked_by_platform"] is True

    blocked = client.post(
        "/api/admin/services/ai_copy/disable", headers=_headers(flower_token, **host)
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "locked_by_platform"


def test_platform_catalog(client):
    token = _platform_token(client)
    response = client.get("/api/platform/catalog", headers=_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert {plan["code"] for plan in data["plans"]} == {"start", "business", "pro"}
    assert len(data["services"]) >= 40
    delivery = next(item for item in data["services"] if item["code"] == "delivery")
    assert delivery["included"]["start"] is False
    assert delivery["included"]["business"] is True


# ─── Биллинг ─────────────────────────────────────────────────────────

BILLING_PHONE = "+375291112299"
BILLING_PASSWORD = "Billing123!"
BILLING_HOST = "billing-shop.localhost"


def _billing_tenant(client) -> dict:
    token = _platform_token(client)
    tenants = client.get(
        "/api/platform/tenants", headers=_headers(token), params={"q": "billing-shop"}
    ).json()["items"]
    existing = next((item for item in tenants if item["slug"] == "billing-shop"), None)
    if existing:
        return existing
    created = client.post(
        "/api/platform/tenants",
        headers=_headers(token),
        json={
            "slug": "billing-shop",
            "name": "Магазин с оплатой",
            "category_preset": "grocery",
            "plan_code": "start",
            "owner_phone": BILLING_PHONE,
            "owner_name": "Владелец биллинга",
            "owner_password": BILLING_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    patched = client.patch(
        f"/api/platform/tenants/{tenant['id']}",
        headers=_headers(token),
        json={"status": "active"},
    )
    assert patched.status_code == 200, patched.text
    return patched.json()


def test_billing_plan_upgrade_requires_payment(client):
    tenant = _billing_tenant(client)
    token = _tenant_token(client, BILLING_PHONE, BILLING_PASSWORD, BILLING_HOST)
    host = {"host": BILLING_HOST}
    platform_token = _platform_token(client)

    overview = client.get("/api/admin/billing", headers=_headers(token, **host))
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data["plan_code"] == "start"
    assert data["price_month"] == 19.0
    assert len(data["plans"]) == 3
    method_codes = {item["code"] for item in data["payment_methods"]}
    assert {"bank_transfer", "card", "erip", "cash"} <= method_codes
    card = next(item for item in data["payment_methods"] if item["code"] == "card")
    assert card["status"] == "setup"

    requested = client.post(
        "/api/admin/billing/plan",
        headers=_headers(token, **host),
        json={"plan_code": "business"},
    )
    assert requested.status_code == 200, requested.text
    result = requested.json()
    assert result["applied"] is False
    assert result["invoice"]["amount"] == 49.0
    assert result["pending_plan_code"] == "business"
    invoice_id = result["invoice"]["id"]

    # Тариф ещё не изменился: счёт только выставлен.
    current = client.get("/api/admin/billing", headers=_headers(token, **host)).json()
    assert current["plan_code"] == "start"
    assert current["pending_plan_code"] == "business"

    invoices = client.get(
        f"/api/platform/tenants/{tenant['id']}/invoices", headers=_headers(platform_token)
    )
    assert invoices.status_code == 200
    assert any(item["id"] == invoice_id and item["status"] == "open" for item in invoices.json())

    paid = client.post(
        f"/api/platform/invoices/{invoice_id}/paid", headers=_headers(platform_token)
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    upgraded = client.get("/api/admin/billing", headers=_headers(token, **host)).json()
    assert upgraded["plan_code"] == "business"
    assert upgraded["price_month"] == 49.0
    assert upgraded["pending_plan_code"] is None

    services = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    by_code = {item["code"]: item for item in services["items"]}
    # Сервис входит в новый тариф и его можно включить без доплаты.
    assert by_code["delivery"]["included_in_plan"] is True
    assert by_code["delivery"]["can_enable"] is True


def test_billing_addon_invoice_and_cancel(client):
    token = _tenant_token(client, BILLING_PHONE, BILLING_PASSWORD, BILLING_HOST)
    host = {"host": BILLING_HOST}
    platform_token = _platform_token(client)
    tenant = _billing_tenant(client)

    requested = client.post(
        "/api/admin/services/sms_marketing/enable", headers=_headers(token, **host)
    )
    assert requested.status_code == 402, requested.text
    detail = requested.json()["detail"]
    assert detail["code"] == "payment_required"
    invoice_id = detail["invoice_id"]

    services = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    addon = next(item for item in services["items"] if item["code"] == "sms_marketing")
    assert addon["status"] == "pending_payment"
    assert addon["enabled"] is False

    paid = client.post(
        f"/api/platform/invoices/{invoice_id}/paid", headers=_headers(platform_token)
    )
    assert paid.status_code == 200, paid.text

    services = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    addon = next(item for item in services["items"] if item["code"] == "sms_marketing")
    assert addon["enabled"] is True
    assert addon["status"] == "enabled"

    manual = client.post(
        f"/api/platform/tenants/{tenant['id']}/invoices",
        headers=_headers(platform_token),
        json={"kind": "manual", "amount": 10, "description": "Дополнительная услуга"},
    )
    assert manual.status_code == 201, manual.text
    manual_id = manual.json()["id"]

    canceled = client.post(
        f"/api/platform/invoices/{manual_id}/cancel",
        headers=_headers(platform_token),
        params={"reason": "Клиент отказался"},
    )
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"

    pay_canceled = client.post(
        f"/api/platform/invoices/{manual_id}/paid", headers=_headers(platform_token)
    )
    assert pay_canceled.status_code == 409


def test_billing_downgrade_is_immediate(client):
    token = _tenant_token(client, BILLING_PHONE, BILLING_PASSWORD, BILLING_HOST)
    host = {"host": BILLING_HOST}

    requested = client.post(
        "/api/admin/billing/plan",
        headers=_headers(token, **host),
        json={"plan_code": "start"},
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["applied"] is True
    assert requested.json()["plan_code"] == "start"

    overview = client.get("/api/admin/billing", headers=_headers(token, **host)).json()
    assert overview["plan_code"] == "start"
    assert overview["price_month"] == 19.0

    services = client.get("/api/admin/services", headers=_headers(token, **host)).json()
    by_code = {item["code"]: item for item in services["items"]}
    assert by_code["delivery"]["enabled"] is False
    assert by_code["catalog"]["enabled"] is True


def test_platform_invoice_list_and_manual_create(client):
    platform_token = _platform_token(client)
    tenant = _billing_tenant(client)

    created = client.post(
        f"/api/platform/tenants/{tenant['id']}/invoices",
        headers=_headers(platform_token),
        json={"kind": "manual", "amount": 25.5, "description": "Настройка витрины"},
    )
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["tenant_id"] == tenant["id"]
    assert invoice["status"] == "open"
    assert invoice["number"].startswith("INV-")

    all_invoices = client.get(
        "/api/platform/invoices",
        headers=_headers(platform_token),
        params={"tenant_id": tenant["id"]},
    )
    assert all_invoices.status_code == 200
    assert any(item["id"] == invoice["id"] for item in all_invoices.json())
