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


# ─── Хостинг, запуск и мониторинг ───────────────────────────────────

OPS_PHONE = "+375291113399"
OPS_PASSWORD = "Ops12345!"
OPS_HOST = "ops-shop.localhost"
OPS_SLUG = "ops-shop"


def _ops_tenant(client) -> dict:
    token = _platform_token(client)
    tenants = client.get(
        "/api/platform/tenants", headers=_headers(token), params={"q": OPS_SLUG}
    ).json()["items"]
    existing = next((item for item in tenants if item["slug"] == OPS_SLUG), None)
    if existing:
        return existing
    created = client.post(
        "/api/platform/tenants",
        headers=_headers(token),
        json={
            "slug": OPS_SLUG,
            "name": "Магазин запуска",
            "category_preset": "grocery",
            "plan_code": "start",
            "owner_phone": OPS_PHONE,
            "owner_name": "Владелец запуска",
            "owner_password": OPS_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_provisioning_queue_and_hosting(client):
    platform_token = _platform_token(client)
    tenant = _ops_tenant(client)

    state = client.get(
        f"/api/platform/tenants/{tenant['id']}/provisioning",
        headers=_headers(platform_token),
    )
    assert state.status_code == 200, state.text
    initial = state.json()
    assert [item["code"] for item in initial["template"]][:2] == ["hosting", "dns"]
    assert initial["hosting"]["deploy_status"] in ("not_started", "queued")

    # Новый магазин попадает в очередь автоматически; POST идемпотентен.
    started = client.post(
        f"/api/platform/tenants/{tenant['id']}/provisioning",
        headers=_headers(platform_token),
    )
    assert started.status_code == 201, started.text
    job = started.json()["job"]
    assert job["status"] == "queued"
    assert job["status_label"] == "В очереди"
    assert job["steps_total"] == 7
    assert job["progress"] == 0

    hosted = client.patch(
        f"/api/platform/tenants/{tenant['id']}/hosting",
        headers=_headers(platform_token),
        json={
            "hosting_provider": "hoster_by",
            "hosting_tariff": "Хостинг Старт",
            "hosting_account": "acc-1042",
            "deploy_url": "https://ops-shop.torgovlia.by",
            "ops_note": "Аккаунт создан, ждём DNS",
        },
    )
    assert hosted.status_code == 200, hosted.text
    hosting = hosted.json()
    assert hosting["hosting_tariff"] == "Хостинг Старт"
    assert hosting["deploy_status"] == "queued"
    assert hosting["primary_host"] == OPS_HOST

    step = client.patch(
        f"/api/platform/provisioning/{job['id']}/steps/hosting",
        headers=_headers(platform_token),
        json={"status": "done", "note": "Аккаунт hoster.by создан"},
    )
    assert step.status_code == 200, step.text
    updated = step.json()
    assert updated["status"] == "in_progress"
    assert updated["progress"] > 0
    assert next(item for item in updated["steps"] if item["code"] == "hosting")["status"] == "done"

    tenant_after = client.get(
        f"/api/platform/tenants/{tenant['id']}", headers=_headers(platform_token)
    ).json()
    assert tenant_after["deploy_status"] == "in_progress"
    assert tenant_after["hosting_account"] == "acc-1042"

    for code, _, _ in [
        ("dns", "", ""), ("ssl", "", ""), ("deploy", "", ""),
        ("mail", "", ""), ("billing", "", ""), ("smoke", "", ""),
    ]:
        done = client.patch(
            f"/api/platform/provisioning/{job['id']}/steps/{code}",
            headers=_headers(platform_token),
            json={"status": "done"},
        )
        assert done.status_code == 200, done.text

    finished = client.get(
        f"/api/platform/tenants/{tenant['id']}/provisioning",
        headers=_headers(platform_token),
    ).json()
    assert finished["job"]["status"] == "done"
    assert finished["job"]["progress"] == 100
    assert finished["hosting"]["deploy_status"] == "deployed"

    overview = client.get("/api/platform/ops/overview", headers=_headers(platform_token))
    assert overview.status_code == 200, overview.text
    data = overview.json()
    item = next(row for row in data["items"] if row["slug"] == OPS_SLUG)
    assert item["deploy_status"] == "deployed"
    assert item["job_id"] == job["id"]
    assert data["tenants_total"] >= 1
    assert "deployed" in data["by_status"]


def test_provisioning_step_validation_and_blocked(client):
    platform_token = _platform_token(client)
    tenant = _ops_tenant(client)
    started = client.post(
        f"/api/platform/tenants/{tenant['id']}/provisioning",
        headers=_headers(platform_token),
    )
    assert started.status_code == 201, started.text
    job = started.json()["job"]

    unknown = client.patch(
        f"/api/platform/provisioning/{job['id']}/steps/unknown",
        headers=_headers(platform_token),
        json={"status": "done"},
    )
    assert unknown.status_code == 404

    bad_status = client.patch(
        f"/api/platform/provisioning/{job['id']}/steps/ssl",
        headers=_headers(platform_token),
        json={"status": "whatever"},
    )
    assert bad_status.status_code == 422

    blocked = client.patch(
        f"/api/platform/provisioning/{job['id']}/steps/dns",
        headers=_headers(platform_token),
        json={"status": "blocked", "note": "Домен занят другим владельцем"},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["steps"][1]["note"] == "Домен занят другим владельцем"

    tenant_after = client.get(
        f"/api/platform/tenants/{tenant['id']}", headers=_headers(platform_token)
    ).json()
    assert tenant_after["deploy_status"] == "failed"


# ─── Жизненный цикл и impersonation ─────────────────────────────────

LIFECYCLE_SLUG = "lifecycle-shop"
LIFECYCLE_PHONE = "+375291113388"
LIFECYCLE_PASSWORD = "Lifecycle123!"


def _lifecycle_tenant(client) -> dict:
    platform_token = _platform_token(client)
    tenants = client.get(
        "/api/platform/tenants", headers=_headers(platform_token), params={"q": LIFECYCLE_SLUG}
    ).json()["items"]
    existing = next((item for item in tenants if item["slug"] == LIFECYCLE_SLUG), None)
    if existing:
        return existing
    created = client.post(
        "/api/platform/tenants",
        headers=_headers(platform_token),
        json={
            "slug": LIFECYCLE_SLUG,
            "name": "Магазин жизненного цикла",
            "category_preset": "grocery",
            "plan_code": "start",
            "owner_phone": LIFECYCLE_PHONE,
            "owner_name": "Владелец цикла",
            "owner_password": LIFECYCLE_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    activated = client.patch(
        f"/api/platform/tenants/{tenant['id']}",
        headers=_headers(platform_token),
        json={"status": "active"},
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


def test_platform_dashboard_metrics(client):
    platform_token = _platform_token(client)
    dashboard = client.get("/api/platform/dashboard", headers=_headers(platform_token))
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    assert data["tenants_total"] >= 1
    assert data["tenants_active"] >= 1
    assert data["mrr"] >= 19.0
    assert data["arr"] == round(data["mrr"] * 12, 2)
    assert data["paying_tenants"] >= 1
    for key in (
        "new_30d",
        "paid_30d",
        "paid_month",
        "open_invoices_total",
        "queue_total",
        "attention_total",
    ):
        assert key in data


def test_lifecycle_suspend_resume_archive(client):
    platform_token = _platform_token(client)
    tenant = _lifecycle_tenant(client)

    state = client.get(
        f"/api/platform/tenants/{tenant['id']}/lifecycle", headers=_headers(platform_token)
    )
    assert state.status_code == 200, state.text
    actions = {item["action"]: item["enabled"] for item in state.json()["actions"]}
    assert actions["suspend"] is True
    assert actions["resume"] is False

    no_reason = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "suspend", "reason": ""},
    )
    assert no_reason.status_code == 422

    suspended = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "suspend", "reason": "Не оплачен счёт за март"},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    by_action = {item["action"]: item["enabled"] for item in suspended.json()["actions"]}
    assert by_action["resume"] is True
    assert by_action["suspend"] is False

    invalid = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "resume", "reason": "Оплата поступила"},
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["status"] == "active"

    twice = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "resume", "reason": "Повторно"},
    )
    assert twice.status_code == 409

    archived = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "archive", "reason": "Клиент закрыл магазин"},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    restored = client.post(
        f"/api/platform/tenants/{tenant['id']}/lifecycle",
        headers=_headers(platform_token),
        json={"action": "restore", "reason": "Клиент вернулся"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "onboarding"


def test_impersonation_token_enters_tenant(client):
    from app.security import decode_token

    platform_token = _platform_token(client)
    tenant = _lifecycle_tenant(client)

    short = client.post(
        f"/api/platform/tenants/{tenant['id']}/impersonate",
        headers=_headers(platform_token),
        json={"reason": "ok"},
    )
    assert short.status_code == 422

    response = client.post(
        f"/api/platform/tenants/{tenant['id']}/impersonate",
        headers=_headers(platform_token),
        json={"reason": "Помощь с настройкой витрины"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["host"] == "lifecycle-shop.localhost"
    assert data["expires_in"] == 1800
    assert data["user"]["phone"] == LIFECYCLE_PHONE

    claims = decode_token(data["access_token"])
    assert claims["imp"] is True
    assert claims["imp_reason"] == "Помощь с настройкой витрины"
    assert claims["scope"] == "tenant"

    me = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {data['access_token']}",
            "host": "lifecycle-shop.localhost",
        },
    )
    assert me.status_code == 200, me.text
    assert me.json()["phone"] == LIFECYCLE_PHONE

    # Токен impersonation не действует в панели платформы.
    platform_me = client.get(
        "/api/platform/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert platform_me.status_code in (401, 403)


def test_demo_mode_selects_tenant_by_header(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "environment", "production")

    response = client.get(
        "/api/site",
        headers={"host": "demo.alwaysdata.net", "X-Tenant-Slug": "flowers"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["settings"]["brand_name"] == "Цветочная лавка"

    platform = client.get("/api/site", headers={"host": "demo.alwaysdata.net"})
    assert platform.status_code == 200
    assert platform.json()["tenant"] is None


def test_platform_alerts_digest_and_telegram(client, monkeypatch):
    from app.config import settings
    from app.platform import alerts as alerts_module

    platform_token = _platform_token(client)
    digest = client.get("/api/platform/alerts", headers=_headers(platform_token))
    assert digest.status_code == 200, digest.text
    data = digest.json()
    assert data["total"] == data["errors"] + data["warnings"]
    assert "Torgovlia" in data["text"]

    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    not_configured = client.post(
        "/api/platform/alerts/telegram",
        headers=_headers(platform_token),
        json={"test": True},
    )
    assert not_configured.status_code == 400

    sent: list[str] = []
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "-100123")
    monkeypatch.setattr(alerts_module, "send_telegram", sent.append)
    ok = client.post(
        "/api/platform/alerts/telegram",
        headers=_headers(platform_token),
        json={"test": True},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["sent"] is True
    assert sent and "тестовое" in sent[0].lower()


# ─── Поддержка магазинов ────────────────────────────────────────────

SUPPORT_OTHER_SLUG = "support-other"
SUPPORT_OTHER_PHONE = "+375291114499"


def _other_tenant(client) -> dict:
    platform_token = _platform_token(client)
    tenants = client.get(
        "/api/platform/tenants", headers=_headers(platform_token), params={"q": SUPPORT_OTHER_SLUG}
    ).json()["items"]
    existing = next((item for item in tenants if item["slug"] == SUPPORT_OTHER_SLUG), None)
    if existing:
        return existing
    created = client.post(
        "/api/platform/tenants",
        headers=_headers(platform_token),
        json={
            "slug": SUPPORT_OTHER_SLUG,
            "name": "Второй магазин поддержки",
            "category_preset": "grocery",
            "plan_code": "start",
            "owner_phone": SUPPORT_OTHER_PHONE,
            "owner_name": "Второй владелец",
            "owner_password": "Support123!",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_support_tickets_flow_and_isolation(client):
    platform_token = _platform_token(client)
    tenant = _lifecycle_tenant(client)
    other = _other_tenant(client)

    created = client.post(
        f"/api/platform/tenants/{tenant['id']}/support",
        headers=_headers(platform_token),
        json={
            "subject": "Не приходят SMS клиентам",
            "body": "Проверили баланс, SMS-шлюз отвечает ошибкой 401.",
            "priority": "high",
        },
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"
    assert ticket["tenant_id"] == tenant["id"]
    assert ticket["closed_at"] is None
    assert ticket["author"]

    listed = client.get(
        f"/api/platform/tenants/{tenant['id']}/support", headers=_headers(platform_token)
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [ticket["id"]]

    isolated = client.get(
        f"/api/platform/tenants/{other['id']}/support", headers=_headers(platform_token)
    )
    assert isolated.status_code == 200
    assert isolated.json() == []

    # Магазин не может читать обращения через панель платформы.
    tenant_token = _admin_token(client)
    forbidden = client.get(
        f"/api/platform/tenants/{tenant['id']}/support", headers=_headers(tenant_token)
    )
    assert forbidden.status_code in (401, 403)

    invalid = client.post(
        f"/api/platform/tenants/{tenant['id']}/support",
        headers=_headers(platform_token),
        json={"subject": "Ошибка", "priority": "urgent"},
    )
    assert invalid.status_code == 422

    closed = client.patch(
        f"/api/platform/support/{ticket['id']}",
        headers=_headers(platform_token),
        json={"status": "closed", "body": "Шлюз перевыпущен, клиенты получили SMS."},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"] is not None
    assert "перевыпущен" in closed.json()["body"]

    reopened = client.patch(
        f"/api/platform/support/{ticket['id']}",
        headers=_headers(platform_token),
        json={"status": "open"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["closed_at"] is None

    missing = client.patch(
        "/api/platform/support/999999",
        headers=_headers(platform_token),
        json={"status": "closed"},
    )
    assert missing.status_code == 404


# ─── Журнал действий ────────────────────────────────────────────────

def test_platform_audit_search_and_export(client):
    platform_token = _platform_token(client)

    failed = client.post(
        "/api/platform/auth/login",
        json={"phone": "+375299990011", "password": "wrong-password"},
    )
    assert failed.status_code == 400

    logins = client.get(
        "/api/platform/audit?action=platform.login",
        headers=_headers(platform_token),
    )
    assert logins.status_code == 200, logins.text
    payload = logins.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["action"] == "platform.login"
    assert payload["items"][0]["platform_user_id"]

    failures = client.get(
        "/api/platform/audit?action=platform.login.failed",
        headers=_headers(platform_token),
    )
    assert failures.status_code == 200, failures.text
    assert failures.json()["total"] >= 1
    assert failures.json()["items"][0]["actor"] == "+375299990011"
    assert failures.json()["items"][0]["details"]["reason"] == "bad_credentials"

    empty = client.get(
        "/api/platform/audit?q=нет-такой-записи-12345",
        headers=_headers(platform_token),
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

    tenant_token = _admin_token(client)
    forbidden = client.get("/api/platform/audit", headers=_headers(tenant_token))
    assert forbidden.status_code in (401, 403)

    export = client.get("/api/platform/audit/export", headers=_headers(platform_token))
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert "attachment" in export.headers["content-disposition"]
    assert export.text.startswith("\ufeffid;created_at_utc;tenant;actor;action")
    assert "platform.login" in export.text


def test_tenant_login_journal(client):
    platform_token = _platform_token(client)
    client.post(
        "/api/auth/login",
        headers={"host": "flower-shop.localhost"},
        json={"phone": FLOWER_PHONE, "password": "wrong-password"},
    )
    failed = client.get(
        "/api/platform/audit?action=user.login.failed&q=" + FLOWER_PHONE.replace("+", "%2B"),
        headers=_headers(platform_token),
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["total"] >= 1
    entry = failed.json()["items"][0]
    assert entry["actor"] == FLOWER_PHONE
    assert entry["tenant_id"]

    client.post(
        "/api/auth/login",
        headers={"host": "flower-shop.localhost"},
        json={"phone": FLOWER_PHONE, "password": FLOWER_PASSWORD},
    )
    ok = client.get(
        "/api/platform/audit?action=user.login&tenant_id=" + str(entry["tenant_id"]),
        headers=_headers(platform_token),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["total"] >= 1


# ─── Инциденты и статус-страница ────────────────────────────────────

def test_incidents_and_public_status(client):
    platform_token = _platform_token(client)

    initial = client.get("/api/status")
    assert initial.status_code == 200, initial.text
    assert initial.json()["overall"] == "operational"
    assert initial.json()["active"] == []

    created = client.post(
        "/api/platform/incidents",
        headers=_headers(platform_token),
        json={
            "title": "Сбой оплаты картой",
            "body": "Платёжный провайдер возвращает ошибку 502.",
            "severity": "critical",
        },
    )
    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["status"] == "investigating"
    assert incident["severity"] == "critical"
    assert incident["tenant_name"] is None
    assert len(incident["updates"]) == 1

    outage = client.get("/api/status")
    assert outage.status_code == 200
    assert outage.json()["overall"] == "outage"
    assert [item["id"] for item in outage.json()["active"]] == [incident["id"]]
    # Публичная страница не раскрывает автора-сотрудника.
    assert "author" not in outage.json()["active"][0]["updates"][0]

    identified = client.post(
        f"/api/platform/incidents/{incident['id']}/updates",
        headers=_headers(platform_token),
        json={"body": "Причина: недоступен шлюз провайдера.", "status": "identified"},
    )
    assert identified.status_code == 201, identified.text
    assert identified.json()["status"] == "identified"
    assert len(identified.json()["updates"]) == 2

    resolved = client.post(
        f"/api/platform/incidents/{incident['id']}/updates",
        headers=_headers(platform_token),
        json={"body": "Провайдер восстановил работу, оплата проходит.", "status": "resolved"},
    )
    assert resolved.status_code == 201, resolved.text
    assert resolved.json()["resolved_at"] is not None

    healthy = client.get("/api/status")
    assert healthy.json()["overall"] == "operational"
    assert healthy.json()["active"] == []
    assert [item["id"] for item in healthy.json()["resolved"]] == [incident["id"]]

    tenant = _lifecycle_tenant(client)
    scoped = client.post(
        "/api/platform/incidents",
        headers=_headers(platform_token),
        json={
            "title": "Не открывается витрина",
            "body": "Проверяем SSL магазина.",
            "severity": "major",
            "tenant_id": tenant["id"],
        },
    )
    assert scoped.status_code == 201, scoped.text
    assert scoped.json()["tenant_id"] == tenant["id"]
    assert scoped.json()["tenant_name"] == tenant["name"]

    listed = client.get(
        "/api/platform/incidents?state=active",
        headers=_headers(platform_token),
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [scoped.json()["id"]]

    tenant_token = _admin_token(client)
    forbidden = client.post(
        "/api/platform/incidents",
        headers=_headers(tenant_token),
        json={"title": "Нельзя", "severity": "minor"},
    )
    assert forbidden.status_code in (401, 403)

    bad_tenant = client.post(
        "/api/platform/incidents",
        headers=_headers(platform_token),
        json={"title": "Нет магазина", "severity": "minor", "tenant_id": 999999},
    )
    assert bad_tenant.status_code == 404
