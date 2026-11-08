from datetime import date, timedelta
from email.message import EmailMessage
from io import BytesIO
import zipfile


def _verify_phone(client, phone: str, purpose: str) -> tuple[str, str]:
    request = client.post("/api/auth/phone/request", json={"phone": phone, "purpose": purpose})
    assert request.status_code == 200, request.text
    data = request.json()
    assert data["debug_code"], "В тестовом режиме код должен возвращаться"
    confirm = client.post(
        "/api/auth/phone/confirm",
        json={"verification_id": data["verification_id"], "code": data["debug_code"]},
    )
    assert confirm.status_code == 200, confirm.text
    return confirm.json()["phone_token"], data["verification_id"]


def _staff_token(client, phone: str, password: str, tenant: str | None = None) -> str:
    headers = {"X-Tenant-Slug": tenant} if tenant else None
    response = client.post(
        "/api/auth/login",
        json={"phone": phone, "password": password},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_seo_sitemap_and_robots(client):
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "urlset" in sitemap.text
    assert "/fish/" in sitemap.text
    assert "<changefreq>daily</changefreq>" in sitemap.text

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap: http://testserver/sitemap.xml" in robots.text
    assert "Disallow: /admin" in robots.text

    demo = client.get("/shop/odezhda/sitemap.xml")
    assert demo.status_code == 200, demo.text
    assert "/shop/odezhda/fish/hudi" in demo.text
    assert "/shop/rybnaya/" not in demo.text

    demo_robots = client.get("/shop/odezhda/robots.txt")
    assert demo_robots.status_code == 200
    assert "Sitemap: http://testserver/shop/odezhda/sitemap.xml" in demo_robots.text

    assert client.get("/shop/nope/sitemap.xml").status_code == 404


def test_seo_settings_and_analytics(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    settings = client.get("/api/admin/settings", headers=headers).json()["settings"]
    original = {
        key: settings.get(key)
        for key in (
            "seo_og_image_url",
            "seo_indexing",
            "analytics_yandex",
            "analytics_google",
            "analytics_meta_pixel",
        )
    }
    settings.update(
        seo_og_image_url="/media/og-cover.png",
        seo_indexing=False,
        analytics_yandex="12345678",
        analytics_google="G-TEST12345",
        analytics_meta_pixel="998877665544332",
    )
    saved = client.put("/api/admin/settings", headers=headers, json=settings)
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["analytics_yandex"] == "12345678"

    public = client.get("/api/site").json()["settings"]
    assert public["seo_indexing"] is False
    assert public["seo_og_image_url"] == "/media/og-cover.png"
    assert public["analytics_google"] == "G-TEST12345"
    assert public["analytics_meta_pixel"] == "998877665544332"

    robots = client.get("/robots.txt").text
    assert "Disallow: /" in robots
    assert "Sitemap:" not in robots

    settings.update(original)
    restored = client.put("/api/admin/settings", headers=headers, json=settings)
    assert restored.status_code == 200, restored.text
    assert client.get("/robots.txt").text.count("Sitemap:") == 1


def test_health_and_catalog(client):
    assert client.get("/api/health").json()["status"] == "ok"
    site = client.get("/api/site").json()
    assert "Барановичи" in site["settings"]["city"]
    assert site["settings"]["unp"]

    products = client.get("/api/products").json()
    assert products["total"] >= 10
    first = products["items"][0]
    assert first["slug"]
    assert first["final_price"] > 0

    detail = client.get(f"/api/products/{first['slug']}").json()
    assert len(detail["description"]) > 300
    assert detail["nutrition"]

    articles = client.get("/api/articles").json()
    assert articles["total"] >= 10


def test_registration_with_sms_and_profile(client):
    phone = "+375291234501"
    token, _ = _verify_phone(client, phone, "register")
    no_consent = client.post(
        "/api/auth/register",
        json={
            "phone_token": token,
            "password": "Passw0rdTest",
            "full_name": "Иван Тестов",
        },
    )
    assert no_consent.status_code == 422

    response = client.post(
        "/api/auth/register",
        json={
            "phone_token": token,
            "password": "Passw0rdTest",
            "full_name": "Иван Тестов",
            "consent_personal_data": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["phone"] == phone
    assert data["user"]["is_phone_verified"] is True
    assert data["user"]["role"] == "customer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "Иван Тестов"

    login = client.post("/api/auth/login", json={"phone": phone, "password": "Passw0rdTest"})
    assert login.status_code == 200

    wrong = client.post("/api/auth/login", json={"phone": phone, "password": "wrong-pass"})
    assert wrong.status_code == 400


def test_registration_requires_verified_phone(client):
    response = client.post(
        "/api/auth/register",
        json={
            "phone_token": "invalid",
            "password": "Passw0rdTest",
            "full_name": "Без Смс",
            "consent_personal_data": True,
        },
    )
    assert response.status_code == 400


def test_guest_order_flow(client):
    products = client.get("/api/products?available_only=true").json()["items"]
    product = next(p for p in products if p["can_order"])
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slots = client.get("/api/slots", params={"date": tomorrow}).json()
    assert slots["is_open"]
    slot = next(s for s in slots["slots"] if s["available"])

    without_token = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Гость",
            "phone": "+375291234502",
            "consent_personal_data": True,
        },
    )
    assert without_token.status_code == 400

    token, _ = _verify_phone(client, "+375291234502", "order")
    no_consent = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Гость",
            "phone": "+375291234502",
            "phone_token": token,
        },
    )
    assert no_consent.status_code == 422

    created = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Гость",
            "phone": "+375291234502",
            "phone_token": token,
            "comment": "Почистить",
            "source": "site",
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["number"].startswith("RL-")
    assert order["status"] == "new"
    assert order["items"][0]["title"] == product["title"]

    lookup = client.post("/api/orders/lookup", json={"number": order["number"], "phone": "+375291234502"})
    assert lookup.status_code == 200

    bad_lookup = client.post("/api/orders/lookup", json={"number": order["number"], "phone": "+375291234500"})
    assert bad_lookup.status_code == 404


def test_registered_user_order_history(client):
    phone = "+375291234503"
    token, _ = _verify_phone(client, phone, "register")
    registration = client.post(
        "/api/auth/register",
        json={
            "phone_token": token,
            "password": "Passw0rdTest",
            "full_name": "Покупатель Тест",
            "consent_personal_data": True,
        },
    ).json()
    headers = {"Authorization": f"Bearer {registration['access_token']}"}

    products = client.get("/api/products?available_only=true").json()["items"]
    product = next(p for p in products if p["can_order"] and p["unit"] == "kg")
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    slots = client.get("/api/slots", params={"date": tomorrow}).json()
    slot = next(s for s in slots["slots"] if s["available"])

    created = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Покупатель Тест",
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["user_id"] == registration["user"]["id"]

    history = client.get("/api/account/orders", headers=headers).json()
    assert history["total"] >= 1

    cancel = client.post(f"/api/account/orders/{order['number']}/cancel", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_admin_panel(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    stats = client.get("/api/admin/stats", headers=headers)
    assert stats.status_code == 200, stats.text
    assert "orders_total" in stats.json()

    settings = client.get("/api/admin/settings", headers=headers)
    assert settings.status_code == 200
    payload = settings.json()["settings"]
    payload["announcement"] = "Тестовое объявление"
    saved = client.put("/api/admin/settings", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["announcement"] == "Тестовое объявление"

    categories = client.get("/api/admin/categories", headers=headers).json()
    assert len(categories["items"]) >= 3

    users = client.get("/api/admin/users", headers=headers).json()
    assert users["total"] >= 1

    seller = next(u for u in users["items"] if u["role"] == "seller")
    promote = client.patch(f"/api/admin/users/{seller['id']}", headers=headers, json={"role": "seller"})
    assert promote.status_code == 200

    qr = client.get("/api/admin/qr/items", headers=headers).json()
    assert qr["items"][0]["kind"] == "site"

    onboarding = client.get("/api/admin/onboarding", headers=headers)
    assert onboarding.status_code == 200, onboarding.text
    data = onboarding.json()
    assert data["total"] == 6
    assert 0 <= data["percent"] <= 100
    codes = {item["code"] for item in data["steps"]}
    assert {"profile", "categories", "products", "logo", "services", "order"} == codes
    assert all(item["href"].startswith("/admin") for item in data["steps"])
    assert any(i["kind"] == "product" for i in qr["items"])

    png = client.get("/api/qr/site.png?size=300")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:4] == b"\x89PNG"

    product_slug = client.get("/api/products").json()["items"][0]["slug"]
    product_qr = client.get(f"/api/qr/product/{product_slug}.png?download=1")
    assert product_qr.status_code == 200
    assert "attachment" in product_qr.headers["content-disposition"]

    orders = client.get("/api/admin/orders", headers=headers).json()
    assert orders["total"] >= 1
    new_order = next(o for o in orders["items"] if o["status"] == "new")
    confirmed = client.patch(
        f"/api/admin/orders/{new_order['id']}",
        headers=headers,
        json={"status": "confirmed", "admin_comment": "Собираем"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    export = client.get("/api/admin/orders/export.csv", headers=headers)
    assert export.status_code == 200
    assert "Номер" in export.content.decode("utf-8-sig")


def test_seller_panel_and_availability(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112244', 'Seller123!')}"}
    summary = client.get("/api/seller/summary", headers=headers)
    assert summary.status_code == 200, summary.text

    created = client.post(
        "/api/seller/products",
        headers=headers,
        json={
            "title": "Тестовая камбала",
            "unit": "kg",
            "price": 12.5,
            "is_available": True,
            "short_description": "Тестовый товар",
        },
    )
    assert created.status_code == 200, created.text
    product = created.json()

    hidden = client.patch(
        f"/api/seller/products/{product['id']}",
        headers=headers,
        json={"is_available": False},
    )
    assert hidden.status_code == 200
    assert hidden.json()["is_available"] is False
    assert hidden.json()["can_order"] is False

    inactive = client.patch(
        f"/api/seller/products/{product['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert inactive.status_code == 200
    catalog = client.get("/api/products", params={"q": "Тестовая камбала"}).json()
    assert catalog["total"] == 0

    customer_blocked = client.get(
        "/api/seller/orders",
        headers={"Authorization": f"Bearer {_staff_token(client, '+375291112255', 'Customer123!')}"},
    )
    assert customer_blocked.status_code == 403


def test_order_rejects_token_with_wrong_purpose(client):
    phone = "+375291234507"
    token, _ = _verify_phone(client, phone, "register")
    product = next(p for p in client.get("/api/products?available_only=true").json()["items"] if p["can_order"])
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slot = next(s for s in client.get("/api/slots", params={"date": tomorrow}).json()["slots"] if s["available"])
    response = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Гость",
            "phone": phone,
            "phone_token": token,
            "consent_personal_data": True,
        },
    )
    assert response.status_code == 400
    assert "не для оформления" in response.json()["detail"]


def test_account_deletion_anonymizes_personal_data(client):
    phone = "+375291234506"
    token, _ = _verify_phone(client, phone, "register")
    registration = client.post(
        "/api/auth/register",
        json={
            "phone_token": token,
            "password": "Passw0rdTest",
            "full_name": "Удаляемый Покупатель",
            "consent_personal_data": True,
        },
    )
    assert registration.status_code == 200, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

    product = next(p for p in client.get("/api/products?available_only=true").json()["items"] if p["can_order"])
    tomorrow = (date.today() + timedelta(days=3)).isoformat()
    slot = next(s for s in client.get("/api/slots", params={"date": tomorrow}).json()["slots"] if s["available"])
    created = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Удаляемый Покупатель",
            "comment": "Позвонить по номеру",
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 200, created.text
    number = created.json()["number"]

    wrong = client.post("/api/account/delete", headers=headers, json={"password": "Passw0rdTest", "confirmation": "нет"})
    assert wrong.status_code == 400

    deleted = client.post(
        "/api/account/delete",
        headers=headers,
        json={"password": "Passw0rdTest", "confirmation": "УДАЛИТЬ"},
    )
    assert deleted.status_code == 200, deleted.text

    assert client.get("/api/auth/me", headers=headers).status_code == 401
    lookup = client.post("/api/orders/lookup", json={"number": number, "phone": phone})
    assert lookup.status_code == 404

    # Освобождённый номер можно зарегистрировать заново.
    again, _ = _verify_phone(client, phone, "register")
    assert again


def test_order_rejects_unavailable_product(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    product = client.get("/api/products").json()["items"][0]
    client.patch(f"/api/admin/products/{product['id']}", headers=headers, json={"is_available": False})

    token, _ = _verify_phone(client, "+375291234504", "order")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    slots = client.get("/api/slots", params={"date": tomorrow}).json()
    slot = next(s for s in slots["slots"] if s["available"])
    response = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Гость",
            "phone": "+375291234504",
            "phone_token": token,
            "consent_personal_data": True,
        },
    )
    assert response.status_code == 400
    assert "наличии" in response.json()["detail"]


def test_design_templates_apply_to_site(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}

    templates = client.get("/api/templates")
    assert templates.status_code == 200, templates.text
    codes = {item["code"] for item in templates.json()}
    assert {"market", "forest", "bloom", "ocean", "mono"}.issubset(codes)
    assert len(codes) >= 8
    ocean = next(item for item in templates.json() if item["code"] == "ocean")
    assert ocean["tokens"]["teal"].startswith("#")

    settings = client.get("/api/admin/settings", headers=headers).json()["settings"]
    original = settings.get("template", "market")
    original_accent = settings.get("accent_color", "")
    settings["template"] = "ocean"
    settings["accent_color"] = "#8c2f5f"
    saved = client.put("/api/admin/settings", headers=headers, json=settings)
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["template"] == "ocean"
    assert saved.json()["settings"]["accent_color"] == "#8c2f5f"

    site = client.get("/api/site").json()
    assert site["settings"]["template"] == "ocean"
    assert site["theme"]["code"] == "ocean"
    assert site["theme"]["accent"] == "#8c2f5f"
    assert site["theme"]["tokens"]["teal"] == "#8c2f5f"
    assert site["theme"]["tokens"]["teal-soft"] != ocean["tokens"]["teal-soft"]

    settings["template"] = original
    settings["accent_color"] = original_accent
    restored = client.put("/api/admin/settings", headers=headers, json=settings)
    assert restored.status_code == 200, restored.text
    final = client.get("/api/site").json()
    assert final["settings"]["template"] == original
    assert final["theme"]["tokens"]["teal"] == next(
        item for item in templates.json() if item["code"] == original
    )["tokens"]["teal"]


def test_promo_codes_apply_to_order(client, tomorrow):
    tenant = {"X-Tenant-Slug": "odezhda"}
    login = client.post(
        "/api/auth/login",
        headers=tenant,
        json={"phone": "+375291112288", "password": "ChangeMe123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", **tenant}

    enabled = client.post("/api/admin/services/promo_codes/enable", headers=headers)
    assert enabled.status_code == 200, enabled.text

    products = client.get("/api/products", headers=tenant).json()["items"]
    product = next(item for item in products if item["slug"] == "hudi")
    slots = client.get("/api/slots", headers=tenant, params={"date": tomorrow}).json()
    assert slots["is_open"], slots
    slot = next(item for item in slots["slots"] if item["available"])

    created = client.post(
        "/api/admin/promo-codes",
        headers=headers,
        json={
            "code": "test10",
            "kind": "percent",
            "value": 10,
            "min_order": 0,
            "max_uses": 1,
            "is_active": True,
            "note": "Тестовая скидка",
        },
    )
    assert created.status_code == 201, created.text
    promo = created.json()
    assert promo["code"] == "TEST10"
    assert promo["status"] == "active"

    check = client.post(
        "/api/promo-codes/validate",
        headers=tenant,
        json={"code": "test10", "subtotal": 100},
    )
    assert check.status_code == 200, check.text
    assert check.json()["discount"] == 10
    assert check.json()["total"] == 90

    order = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Стилист",
            "promo_code": "test10",
            "consent_personal_data": True,
        },
    )
    assert order.status_code == 200, order.text
    data = order.json()
    assert data["promo_code"] == "TEST10"
    assert data["discount_amount"] == 7.9
    assert data["total_amount"] == 71.1

    exhausted = client.post(
        "/api/promo-codes/validate",
        headers=tenant,
        json={"code": "TEST10", "subtotal": 100},
    )
    assert exhausted.status_code == 400
    assert "Лимит" in exhausted.json()["detail"]

    delete = client.delete(f"/api/admin/promo-codes/{promo['id']}", headers=headers)
    assert delete.status_code == 409

    listed = client.get("/api/admin/promo-codes", headers=headers).json()
    stored = next(item for item in listed if item["code"] == "TEST10")
    assert stored["used_count"] == 1

    # Отмена брони возвращает использование промокода.
    cancel = client.patch(
        f"/api/admin/orders/{data['id']}",
        headers=headers,
        json={"status": "cancelled"},
    )
    assert cancel.status_code == 200, cancel.text
    released = client.post(
        "/api/promo-codes/validate",
        headers=tenant,
        json={"code": "TEST10", "subtotal": 100},
    )
    assert released.status_code == 200, released.text
    assert released.json()["discount"] == 10


def test_reviews_moderation_and_rating(client):
    tenant = {"X-Tenant-Slug": "odezhda"}
    login = client.post(
        "/api/auth/login",
        headers=tenant,
        json={"phone": "+375291112288", "password": "ChangeMe123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", **tenant}

    enabled = client.post("/api/admin/services/reviews/enable", headers=headers)
    assert enabled.status_code == 200, enabled.text

    products = client.get("/api/products", headers=tenant).json()["items"]
    product = next(item for item in products if item["slug"] == "hudi")

    fresh = client.get("/api/products/hudi/reviews", headers=tenant)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["enabled"] is True
    assert fresh.json()["total"] == 0

    created = client.post(
        "/api/products/hudi/reviews",
        headers=tenant,
        json={
            "customer_name": "Покупатель Тестов",
            "phone": "+375291112288",
            "rating": 5,
            "text": "Отличная вещь, ткань приятная и размер подошёл.",
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 201, created.text
    review = created.json()
    assert review["status"] == "pending"

    hidden = client.get("/api/products/hudi/reviews", headers=tenant).json()
    assert hidden["total"] == 0

    pending = client.get("/api/admin/reviews", headers=headers).json()
    assert any(item["id"] == review["id"] for item in pending)

    published = client.patch(
        f"/api/admin/reviews/{review['id']}",
        headers=headers,
        json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    public = client.get("/api/products/hudi/reviews", headers=tenant).json()
    assert public["total"] == 1
    assert public["average"] == 5.0
    assert public["items"][0]["customer_name"] == "Покупатель Тестов"
    assert public["items"][0]["phone_formatted"] == ""

    detail = client.get("/api/products/hudi", headers=tenant).json()
    assert detail["rating"] == 5.0
    assert detail["reviews_count"] == 1

    second = client.post(
        "/api/products/hudi/reviews",
        headers=tenant,
        json={
            "customer_name": "Второй Покупатель",
            "phone": "+375291112288",
            "rating": 3,
            "text": "Нормально, но ожидал другой оттенок.",
            "consent_personal_data": True,
        },
    )
    assert second.status_code == 201, second.text
    client.patch(
        f"/api/admin/reviews/{second.json()['id']}",
        headers=headers,
        json={"status": "published"},
    )
    mixed = client.get("/api/products/hudi/reviews", headers=tenant).json()
    assert mixed["total"] == 2
    assert mixed["average"] == 4.0

    for item in (review, second.json()):
        removed = client.delete(f"/api/admin/reviews/{item['id']}", headers=headers)
        assert removed.status_code == 204
    empty = client.get("/api/products/hudi/reviews", headers=tenant).json()
    assert empty["total"] == 0


def test_delivery_zones_and_order(client, tomorrow):
    tenant = {"X-Tenant-Slug": "odezhda"}
    login = client.post(
        "/api/auth/login",
        headers=tenant,
        json={"phone": "+375291112288", "password": "ChangeMe123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", **tenant}

    enabled = client.post("/api/admin/services/delivery/enable", headers=headers)
    assert enabled.status_code == 200, enabled.text

    zones = client.get("/api/delivery/zones", headers=tenant).json()
    assert zones, zones
    zone = next(item for item in zones if item["min_order"] <= 79)
    assert zone["is_active"] is True

    site = client.get("/api/site", headers=tenant).json()
    assert site["features"]["delivery"] is True

    products = client.get("/api/products", headers=tenant).json()["items"]
    product = next(item for item in products if item["slug"] == "hudi")
    slots = client.get("/api/slots", headers=tenant, params={"date": tomorrow}).json()
    slot = next(item for item in slots["slots"] if item["available"])

    order = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Доставка Тест",
            "fulfillment": "delivery",
            "delivery_zone_id": zone["id"],
            "delivery_address": "г. Барановичи, ул. Советская, 10, кв. 5",
            "consent_personal_data": True,
        },
    )
    assert order.status_code == 200, order.text
    data = order.json()
    assert data["fulfillment"] == "delivery"
    assert data["delivery_zone_name"] == zone["name"]
    assert data["delivery_address"].startswith("г. Барановичи")
    assert data["delivery_fee"] > 0
    assert data["total_amount"] == round(product["final_price"] + data["delivery_fee"], 2)

    no_zone = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Без Зоны",
            "fulfillment": "delivery",
            "delivery_address": "г. Барановичи, ул. Советская, 10",
            "consent_personal_data": True,
        },
    )
    assert no_zone.status_code == 400
    assert "зону" in no_zone.json()["detail"].lower()

    short_address = client.post(
        "/api/orders",
        headers=headers,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Короткий Адрес",
            "fulfillment": "delivery",
            "delivery_zone_id": zone["id"],
            "delivery_address": "дом",
            "consent_personal_data": True,
        },
    )
    assert short_address.status_code == 400
    assert "адрес" in short_address.json()["detail"].lower()


def test_reports_and_export(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    report = client.get("/api/admin/reports?days=30", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["range"]["days"] == 30
    assert len(data["daily"]) == 30
    assert set(data["kpis"]) >= {"orders", "completed", "revenue", "avg_check", "new_customers"}
    assert {row["code"] for row in data["statuses"]} >= {"new", "completed", "cancelled"}
    assert isinstance(data["top_products"], list)
    assert isinstance(data["categories"], list)

    for kind in ("daily", "products", "categories", "statuses", "orders"):
        exported = client.get(f"/api/admin/reports/export.csv?kind={kind}&days=30", headers=headers)
        assert exported.status_code == 200, exported.text
        assert "text/csv" in exported.headers["content-type"]
        assert exported.content.startswith(b"\xef\xbb\xbf")

    assert client.get("/api/admin/reports/export.csv?kind=wrong", headers=headers).status_code == 422


def test_notification_settings(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    data = client.get("/api/admin/notifications", headers=headers)
    assert data.status_code == 200, data.text
    payload = data.json()
    assert "channels" in payload
    original = payload["settings"]

    saved = client.put(
        "/api/admin/notifications",
        headers=headers,
        json={
            "notify_on_new_order": True,
            "notify_on_cancel": False,
            "notify_telegram_chat": "123456789",
            "notify_sms_phone": "+375291112233",
            "notify_email": "owner@example.by",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["notify_telegram_chat"] == "123456789"

    public = client.get("/api/site").json()["settings"]
    assert "notify_telegram_chat" not in public
    assert "notify_sms_phone" not in public

    telegram = client.post(
        "/api/admin/notifications/test",
        headers=headers,
        json={"channel": "telegram"},
    )
    assert telegram.status_code == 400
    assert "Telegram" in telegram.json()["detail"]

    sms = client.post(
        "/api/admin/notifications/test",
        headers=headers,
        json={"channel": "sms", "target": "+375291112233"},
    )
    assert sms.status_code == 200, sms.text
    assert sms.json()["sent"] is True

    restored = client.put("/api/admin/notifications", headers=headers, json=original)
    assert restored.status_code == 200, restored.text


def test_inventory_movements_and_order_stock(client, tomorrow):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    products = client.get("/api/products?available_only=true").json()["items"]
    product = next(p for p in products if p["can_order"])
    initial = product["stock"]

    adjusted = client.post(
        f"/api/admin/inventory/{product['id']}/movement",
        headers=headers,
        json={"kind": "adjust", "quantity": 10, "reason": "Тестовая инвентаризация"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["stock"] == 10

    inventory = client.get("/api/admin/inventory", headers=headers).json()
    row = next(item for item in inventory["items"] if item["id"] == product["id"])
    assert row["stock"] == 10
    assert row["is_out"] is False

    out = client.post(
        f"/api/admin/inventory/{product['id']}/movement",
        headers=headers,
        json={"kind": "out", "quantity": 3, "reason": "Порча"},
    )
    assert out.status_code == 200, out.text
    assert out.json()["stock"] == 7

    too_much = client.post(
        f"/api/admin/inventory/{product['id']}/movement",
        headers=headers,
        json={"kind": "out", "quantity": 100},
    )
    assert too_much.status_code == 400

    slots = client.get("/api/slots", params={"date": tomorrow}).json()
    slot = next(s for s in slots["slots"] if s["available"])
    phone = "+375291234509"
    token, _ = _verify_phone(client, phone, "order")
    created = client.post(
        "/api/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 2}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Склад Тест",
            "phone": phone,
            "phone_token": token,
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()

    after_order = client.get(
        "/api/admin/inventory/movements",
        params={"product_id": product["id"]},
        headers=headers,
    ).json()["items"]
    order_move = next(item for item in after_order if item["kind"] == "order")
    assert order_move["quantity"] == -2
    assert order_move["stock_after"] == 5
    assert order["number"] in order_move["reason"]

    cancelled = client.patch(
        f"/api/admin/orders/{order['id']}",
        headers=headers,
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text

    after_cancel = client.get(
        "/api/admin/inventory/movements",
        params={"product_id": product["id"]},
        headers=headers,
    ).json()["items"]
    cancel_move = next(item for item in after_cancel if item["kind"] == "cancel")
    assert cancel_move["quantity"] == 2
    assert cancel_move["stock_after"] == 7

    low = client.get("/api/admin/inventory?low_only=true&threshold=20", headers=headers).json()
    assert any(item["id"] == product["id"] for item in low["items"])

    if initial is None:
        final = client.post(
            f"/api/admin/inventory/{product['id']}/movement",
            headers=headers,
            json={"kind": "adjust", "quantity": 0, "reason": "Сброс теста"},
        )
        assert final.status_code == 200
    else:
        final = client.post(
            f"/api/admin/inventory/{product['id']}/movement",
            headers=headers,
            json={"kind": "adjust", "quantity": initial, "reason": "Сброс теста"},
        )
        assert final.status_code == 200
        assert final.json()["stock"] == initial


def test_suppliers_and_purchase_receiving(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    supplier = client.post(
        "/api/admin/suppliers",
        headers=headers,
        json={
            "name": "ООО «Тестовая поставка»",
            "contact_person": "Пётр Снабженец",
            "phone": "+375291119999",
            "email": "supply@example.by",
            "address": "г. Минск, ул. Складская, 1",
            "note": "Отсрочка 7 дней",
            "is_active": True,
        },
    )
    assert supplier.status_code == 201, supplier.text
    supplier_data = supplier.json()
    assert supplier_data["name"] == "ООО «Тестовая поставка»"

    listed = client.get("/api/admin/suppliers", headers=headers).json()
    assert any(item["id"] == supplier_data["id"] for item in listed["items"])

    updated = client.patch(
        f"/api/admin/suppliers/{supplier_data['id']}",
        headers=headers,
        json={"contact_person": "Пётр Петров", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["contact_person"] == "Пётр Петров"
    assert updated.json()["is_active"] is False

    products = client.get("/api/products?available_only=true").json()["items"]
    product = next(p for p in products if p["can_order"])
    initial = product["stock"]
    purchase = client.post(
        "/api/admin/purchases",
        headers=headers,
        json={
            "supplier_id": supplier_data["id"],
            "expected_date": (date.today() + timedelta(days=2)).isoformat(),
            "note": "Тестовая накладная",
            "items": [{"product_id": product["id"], "quantity": 4, "cost": 2.5}],
        },
    )
    assert purchase.status_code == 201, purchase.text
    purchase_data = purchase.json()
    assert purchase_data["status"] == "draft"
    assert purchase_data["total_amount"] == 10
    assert purchase_data["supplier_name"] == "ООО «Тестовая поставка»"
    assert purchase_data["items"][0]["title"] == product["title"]

    received = client.patch(
        f"/api/admin/purchases/{purchase_data['id']}",
        headers=headers,
        json={"status": "received"},
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"
    assert received.json()["received_at"]

    stock_after = client.get("/api/admin/inventory", headers=headers).json()
    row = next(item for item in stock_after["items"] if item["id"] == product["id"])
    assert row["stock"] == (initial or 0) + 4

    movements = client.get(
        "/api/admin/inventory/movements",
        params={"product_id": product["id"]},
        headers=headers,
    ).json()["items"]
    supply_move = next(item for item in movements if item["kind"] == "in" and purchase_data["number"] in item["reason"])
    assert supply_move["quantity"] == 4

    repeated = client.patch(
        f"/api/admin/purchases/{purchase_data['id']}",
        headers=headers,
        json={"status": "received"},
    )
    assert repeated.status_code == 400

    cancelled = client.post(
        "/api/admin/purchases",
        headers=headers,
        json={
            "supplier_id": None,
            "items": [{"product_id": product["id"], "quantity": 1, "cost": 1}],
        },
    )
    assert cancelled.status_code == 201, cancelled.text
    cancelled_data = cancelled.json()
    assert client.patch(
        f"/api/admin/purchases/{cancelled_data['id']}",
        headers=headers,
        json={"status": "cancelled"},
    ).status_code == 200
    assert client.delete(
        f"/api/admin/purchases/{cancelled_data['id']}",
        headers=headers,
    ).status_code == 204

    assert client.delete(f"/api/admin/suppliers/{supplier_data['id']}", headers=headers).status_code == 204

    restore = client.post(
        f"/api/admin/inventory/{product['id']}/movement",
        headers=headers,
        json={"kind": "adjust", "quantity": initial or 0, "reason": "Сброс теста закупки"},
    )
    assert restore.status_code == 200
    assert restore.json()["stock"] == (initial or 0)


def _ean13_check(base: str) -> str:
    total = sum(int(char) * (3 if index % 2 else 1) for index, char in enumerate(base))
    return str((10 - total % 10) % 10)


def test_barcodes_backfill_lookup_and_labels(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}

    backfill = client.post("/api/admin/barcodes/backfill", headers=headers)
    assert backfill.status_code == 200, backfill.text
    assert backfill.json()["updated"] >= 1

    products = client.get("/api/admin/products?limit=1000", headers=headers).json()["items"]
    assert products
    for product in products:
        assert product["barcode"], product["title"]
        assert len(product["barcode"]) == 13
        assert product["barcode"].isdigit()
        assert _ean13_check(product["barcode"][:12]) == product["barcode"][12]

    sample = products[0]
    found = client.get(
        "/api/admin/barcodes/lookup",
        params={"code": sample["barcode"]},
        headers=headers,
    )
    assert found.status_code == 200, found.text
    assert found.json()["id"] == sample["id"]
    assert found.json()["barcode"] == sample["barcode"]

    missing = client.get(
        "/api/admin/barcodes/lookup",
        params={"code": "2000000000000"},
        headers=headers,
    )
    assert missing.status_code == 404

    custom = "20" + "0000000123" + _ean13_check("20" + "0000000123")
    created = client.post(
        "/api/admin/products",
        headers=headers,
        json={
            "title": "Товар со своим штрихкодом",
            "price": 9.9,
            "unit": "piece",
            "barcode": custom,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["barcode"] == custom

    duplicate = client.post(
        "/api/admin/products",
        headers=headers,
        json={
            "title": "Товар с занятым штрихкодом",
            "price": 1,
            "unit": "piece",
            "barcode": custom,
        },
    )
    assert duplicate.status_code == 400

    invalid = client.patch(
        f"/api/admin/products/{created.json()['id']}",
        headers=headers,
        json={"barcode": "2000000000001"},
    )
    assert invalid.status_code == 400

    regenerated = client.post(f"/api/admin/products/{created.json()['id']}/barcode", headers=headers)
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["barcode"] != custom
    assert _ean13_check(regenerated.json()["barcode"][:12]) == regenerated.json()["barcode"][12]

    assert client.delete(f"/api/admin/products/{created.json()['id']}?hard=true", headers=headers).status_code in (200, 204)


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    def column(index: int) -> str:
        name = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    body = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            ref = f"{column(column_index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{namespace}"><sheetData>{"".join(body)}</sheetData></worksheet>'
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def test_price_import_csv_preview_apply_and_history(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}
    products = client.get("/api/admin/products?limit=1000", headers=headers).json()["items"]
    sample = next(product for product in products if product["is_active"])
    old_price = sample["price"]
    old_stock = sample["stock"]

    csv_text = (
        "Наименование;Цена;Остаток;Штрихкод;Единица;Категория\n"
        f"{sample['title']};123,45;7;{sample['barcode']};кг;Рыба\n"
        "Импортированный товар;10,50;3;;шт.;Импорт\n"
    )
    preview = client.post(
        "/api/admin/imports/preview",
        headers=headers,
        data={"text": csv_text},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["total"] == 2
    assert data["matched"] == 1
    assert data["new"] == 1
    matched = next(row for row in data["rows"] if row["status"] == "matched")
    assert matched["product_id"] == sample["id"]
    fresh = next(row for row in data["rows"] if row["status"] == "new")
    assert fresh["price"] == 10.5

    rows = []
    for row in data["rows"]:
        rows.append(
            {
                "line": row["line"],
                "title": row["title"],
                "price": row["price"],
                "stock": row["stock"],
                "barcode": row["barcode"],
                "unit": row["unit"],
                "category": row["category"],
                "product_id": row["product_id"],
                "action": "update" if row["status"] == "matched" else "create",
            }
        )
    applied = client.post(
        "/api/admin/imports/apply",
        headers=headers,
        json={
            "filename": "price.csv",
            "source": "csv",
            "rows": rows,
            "update_prices": True,
            "update_stock": True,
            "create_missing": True,
        },
    )
    assert applied.status_code == 200, applied.text
    batch = applied.json()
    assert batch["updated"] == 1
    assert batch["created"] == 1
    assert batch["errors"] == 0

    updated = client.get(f"/api/admin/products/{sample['id']}", headers=headers).json()
    assert updated["price"] == 123.45
    assert updated["stock"] == 7

    created_id = next(
        row["id"]
        for row in client.get("/api/admin/products?limit=1000", headers=headers).json()["items"]
        if row["title"] == "Импортированный товар"
    )
    created = client.get(f"/api/admin/products/{created_id}", headers=headers).json()
    assert created["price"] == 10.5
    assert created["stock"] == 3
    assert created["barcode"]

    movements = client.get(
        "/api/admin/inventory/movements",
        params={"product_id": sample["id"]},
        headers=headers,
    ).json()["items"]
    assert any("Импорт прайса" in movement["reason"] for movement in movements)

    history = client.get("/api/admin/imports", headers=headers).json()
    assert history["total"] >= 1
    assert history["items"][0]["filename"] == "price.csv"

    template = client.get("/api/admin/imports/template.csv", headers=headers)
    assert template.status_code == 200
    assert "Название;Цена" in template.text

    assert client.patch(
        f"/api/admin/products/{sample['id']}",
        headers=headers,
        json={"price": old_price, "stock": old_stock},
    ).status_code == 200
    assert client.delete(f"/api/admin/products/{created_id}?hard=true", headers=headers).status_code in (200, 204)


def test_price_import_xlsx_and_email_preview(client):
    headers = {"Authorization": f"Bearer {_staff_token(client, '+375291112233', 'ChangeMe123!')}"}

    xlsx = _xlsx_bytes([
        ["Название", "Цена", "Остаток", "Штрихкод"],
        ["Товар из Excel", "15,90", "4", ""],
    ])
    preview = client.post(
        "/api/admin/imports/preview",
        headers=headers,
        files={"file": ("price.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert preview.status_code == 200, preview.text
    xlsx_data = preview.json()
    assert xlsx_data["source"] == "xlsx"
    assert xlsx_data["rows"][0]["title"] == "Товар из Excel"
    assert xlsx_data["rows"][0]["price"] == 15.9
    assert xlsx_data["rows"][0]["stock"] == 4

    message = EmailMessage()
    message["Subject"] = "Прайс на неделю"
    message["From"] = "supplier@example.by"
    message["To"] = "shop@example.by"
    message.set_content("Прайс во вложении")
    message.add_attachment(
        "Название;Цена\nТовар из письма;7,25\n".encode("utf-8"),
        maintype="text",
        subtype="csv",
        filename="price.csv",
    )
    email_preview = client.post(
        "/api/admin/imports/preview",
        headers=headers,
        files={"file": ("mail.eml", message.as_bytes(), "message/rfc822")},
    )
    assert email_preview.status_code == 200, email_preview.text
    email_data = email_preview.json()
    assert email_data["source"] == "eml"
    assert email_data["rows"][0]["title"] == "Товар из письма"
    assert email_data["rows"][0]["price"] == 7.25

    unsupported = client.post(
        "/api/admin/imports/preview",
        headers=headers,
        files={"file": ("old.xls", b"binary", "application/vnd.ms-excel")},
    )
    assert unsupported.status_code == 400


def test_campaigns_segments_demo_send_and_history(client):
    from app.config import settings

    headers = {
        "Authorization": f"Bearer {_staff_token(client, '+375291112288', 'ChangeMe123!', tenant='odezhda')}",
        "X-Tenant-Slug": "odezhda",
    }

    meta = client.get("/api/admin/campaigns/meta", headers=headers)
    assert meta.status_code == 200, meta.text
    meta_data = meta.json()
    assert {item["code"] for item in meta_data["segments"]} >= {"all", "with_orders", "inactive", "vip"}
    all_counts = next(item for item in meta_data["segments"] if item["code"] == "all")
    assert all_counts["email"] >= 6
    assert all_counts["sms"] >= 6
    assert meta_data["channels"]["email"] in (True, False)

    audience = client.post(
        "/api/admin/campaigns/audience",
        headers=headers,
        json={"channel": "email", "segment": "all", "filters": {}},
    )
    assert audience.status_code == 200, audience.text
    audience_data = audience.json()
    assert audience_data["total"] >= 6
    assert audience_data["sample"]
    assert "@" in audience_data["sample"][0]["contact"]

    sms_audience = client.post(
        "/api/admin/campaigns/audience",
        headers=headers,
        json={"channel": "sms", "segment": "no_orders", "filters": {"min_orders": 0}},
    )
    assert sms_audience.status_code == 200
    assert all(item["contact"].startswith("+") for item in sms_audience.json()["sample"])

    created = client.post(
        "/api/admin/campaigns",
        headers=headers,
        json={
            "name": "Осенняя акция",
            "channel": "email",
            "subject": "Скидки в {shop}",
            "body": "Здравствуйте, {name}! Скидка 10% на всё.",
            "segment": "all",
            "filters": {},
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["status"] == "draft"
    campaign_id = campaign["id"]

    blocked = client.post(f"/api/admin/campaigns/{campaign_id}/launch", headers=headers)
    assert blocked.status_code == 400
    assert "Канал не настроен" in blocked.json()["detail"]

    settings.demo_mode = True
    try:
        launched = client.post(f"/api/admin/campaigns/{campaign_id}/launch", headers=headers)
        assert launched.status_code == 200, launched.text
        assert launched.json()["recipients_count"] >= 6

        import time

        final = {}
        for _ in range(40):
            history = client.get("/api/admin/campaigns", headers=headers).json()
            final = next(item for item in history["items"] if item["id"] == campaign_id)
            if final["status"] == "sent":
                break
            time.sleep(0.05)
        assert final["status"] == "sent"
        assert final["sent_count"] == final["recipients_count"]
        assert final["demo_count"] == final["recipients_count"]
        assert final["failed_count"] == 0

        recipients = client.get(
            f"/api/admin/campaigns/{campaign_id}/recipients", headers=headers
        ).json()
        assert recipients["total"] >= 6
        assert all(item["status"] == "demo" for item in recipients["items"])
    finally:
        settings.demo_mode = False

    updated = client.patch(
        f"/api/admin/campaigns/{campaign_id}",
        headers=headers,
        json={"name": "Поздняя правка"},
    )
    assert updated.status_code == 409

    draft = client.post(
        "/api/admin/campaigns",
        headers=headers,
        json={
            "name": "SMS черновик",
            "channel": "sms",
            "body": "Акция {shop}: скидка 10% до воскресенья.",
            "segment": "all",
        },
    )
    assert draft.status_code == 201
    assert draft.json()["channel"] == "sms"
    assert client.delete(
        f"/api/admin/campaigns/{draft.json()['id']}", headers=headers
    ).status_code == 204


def test_carts_abandoned_reminder_and_upsells(client):
    from app.config import settings
    from app.services import carts as carts_service

    headers = {
        "Authorization": f"Bearer {_staff_token(client, '+375291112288', 'ChangeMe123!', tenant='odezhda')}",
        "X-Tenant-Slug": "odezhda",
    }
    public = {"X-Tenant-Slug": "odezhda"}
    products = client.get("/api/products?limit=50", headers=public).json()["items"]
    assert len(products) >= 2
    first, second = products[0], products[1]

    sync = client.post(
        "/api/cart/sync",
        headers=public,
        json={
            "session_key": "test-cart-session-1",
            "items": [
                {"product_id": first["id"], "quantity": 2},
                {"product_id": second["id"], "quantity": 1},
            ],
            "name": "Тестовый Покупатель",
            "phone": "+375291119999",
            "email": "cart@example.by",
        },
    )
    assert sync.status_code == 200, sync.text
    assert sync.json()["stored"] is True
    assert sync.json()["items"] == 2

    active = client.get("/api/admin/carts?status=active", headers=headers)
    assert active.status_code == 200, active.text
    cart = next(item for item in active.json()["items"] if item["phone_raw"] == "+375291119999")
    assert cart["items_count"] == 2
    assert cart["total"] > 0
    assert cart["abandoned"] is False

    original = carts_service.ABANDON_MINUTES
    carts_service.ABANDON_MINUTES = 0
    try:
        abandoned = client.get("/api/admin/carts?status=abandoned", headers=headers).json()
        listed = next(item for item in abandoned["items"] if item["id"] == cart["id"])
        assert listed["abandoned"] is True
        assert abandoned["summary"]["abandoned"] >= 1

        settings.demo_mode = True
        try:
            reminded = client.post(f"/api/admin/carts/{cart['id']}/remind", headers=headers)
            assert reminded.status_code == 200, reminded.text
            assert reminded.json()["sent"] is True
            assert reminded.json()["demo"] is True
            assert reminded.json()["channel"] == "email"

            again = client.post(f"/api/admin/carts/{cart['id']}/remind", headers=headers)
            assert again.status_code == 409

            bulk = client.post("/api/admin/carts/remind-all", headers=headers)
            assert bulk.status_code == 200
            assert bulk.json()["skipped"] >= 1
        finally:
            settings.demo_mode = False
    finally:
        carts_service.ABANDON_MINUTES = original

    upsell = client.put(
        f"/api/admin/upsells/{first['id']}",
        headers=headers,
        json={"items": [second["id"]], "is_active": True},
    )
    assert upsell.status_code == 200, upsell.text
    assert upsell.json()["items"][0]["id"] == second["id"]

    related = client.get(f"/api/products/{first['slug']}/related", headers=public)
    assert related.status_code == 200
    assert related.json()["items"][0]["id"] == second["id"]

    rules = client.get("/api/admin/upsells", headers=headers).json()["items"]
    assert any(rule["product_id"] == first["id"] for rule in rules)

    assert client.delete(f"/api/admin/upsells/{first['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/admin/carts/{cart['id']}", headers=headers).status_code == 204


def test_loyalty_earn_redeem_refund_and_levels(client, tomorrow):
    from decimal import Decimal

    tenant = {"X-Tenant-Slug": "odezhda"}
    staff = {
        "Authorization": f"Bearer {_staff_token(client, '+375291112288', 'ChangeMe123!', tenant='odezhda')}",
        **tenant,
    }
    login = client.post(
        "/api/auth/login",
        headers=tenant,
        json={"phone": "+375291113301", "password": "Customer123!"},
    )
    assert login.status_code == 200, login.text
    customer = {"Authorization": f"Bearer {login.json()['access_token']}", **tenant}

    enabled = client.post("/api/admin/services/loyalty/enable", headers=staff)
    assert enabled.status_code == 200, enabled.text
    features = client.get("/api/site", headers=tenant).json()["features"]
    assert features["loyalty"] is True

    overview = client.get("/api/admin/loyalty", headers=staff)
    assert overview.status_code == 200, overview.text
    settings = overview.json()["settings"]
    assert settings["earn_per_byn"] == 5
    assert settings["point_value"] == 0.01
    assert [level["title"] for level in settings["levels"]] == ["Бронза", "Серебро", "Золото"]

    products = client.get("/api/products", headers=tenant).json()["items"]
    product = next(item for item in products if item["slug"] == "hudi")
    price = Decimal(str(product["final_price"]))
    article = product["id"]
    slots = client.get("/api/slots", headers=tenant, params={"date": tomorrow}).json()
    slot = next(item for item in slots["slots"] if item["available"])

    def place_order(points_used: int = 0) -> dict:
        response = client.post(
            "/api/orders",
            headers=customer,
            json={
                "items": [{"product_id": article, "quantity": 1}],
                "pickup_date": tomorrow,
                "pickup_time": slot["time"],
                "customer_name": "Анна Ковалёва",
                "points_used": points_used,
                "consent_personal_data": True,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def complete(order_id: int):
        for status in ("confirmed", "ready", "completed"):
            response = client.patch(
                f"/api/admin/orders/{order_id}", headers=staff, json={"status": status}
            )
            assert response.status_code == 200, response.text
        return response

    first = place_order()
    assert first["points_used"] == 0
    completed = complete(first["id"])
    earned = int(price * 5)
    assert completed.json()["points_earned"] == earned

    account = client.get("/api/account/loyalty", headers=customer)
    assert account.status_code == 200, account.text
    data = account.json()
    assert data["enabled"] is True
    assert data["balance"] == earned
    assert data["earned_total"] == earned
    assert data["level"] == "bronze"
    assert data["transactions"][0]["kind"] == "earn"

    listed = client.get("/api/admin/loyalty", headers=staff).json()
    row = next(item for item in listed["items"] if item["phone_raw"] == "+375291113301")
    assert row["balance"] == earned

    adjusted = client.post(
        f"/api/admin/loyalty/accounts/{row['id']}/adjust",
        headers=staff,
        json={"points": 1000 - earned, "note": "Тестовое начисление"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["balance"] == 1000
    assert adjusted.json()["level"] == "silver"
    assert adjusted.json()["level_info"]["title"] == "Серебро"

    too_few = client.post(
        "/api/orders",
        headers=customer,
        json={
            "items": [{"product_id": article, "quantity": 1}],
            "pickup_date": tomorrow,
            "pickup_time": slot["time"],
            "customer_name": "Анна Ковалёва",
            "points_used": 50,
            "consent_personal_data": True,
        },
    )
    assert too_few.status_code == 400
    assert "Минимум" in too_few.json()["detail"]

    redeemed = place_order(300)
    assert redeemed["points_used"] == 300
    assert redeemed["points_discount"] == 3
    assert redeemed["total_amount"] == float(price - Decimal("3"))

    balance_after_redeem = client.get("/api/account/loyalty", headers=customer).json()["balance"]
    assert balance_after_redeem == 700
    refund = client.patch(
        f"/api/admin/orders/{redeemed['id']}", headers=staff, json={"status": "cancelled"}
    )
    assert refund.status_code == 200, refund.text
    assert refund.json()["points_used"] == 0
    restored = client.get("/api/account/loyalty", headers=customer).json()
    assert restored["balance"] == 1000
    assert any(item["kind"] == "refund" for item in restored["transactions"])

    second = place_order(300)
    finished = complete(second["id"])
    goods = Decimal(str(finished.json()["total_amount"]))
    expected_earn = int(goods * Decimal("5") * Decimal("1.25"))
    assert finished.json()["points_earned"] == expected_earn
    final = client.get("/api/account/loyalty", headers=customer).json()
    assert final["balance"] == 1000 - 300 + expected_earn
    assert final["level"] == "silver"

    saved = client.put(
        "/api/admin/loyalty/settings",
        headers=staff,
        json={
            "is_active": True,
            "earn_per_byn": 10,
            "point_value": 0.02,
            "max_redeem_percent": 50,
            "min_redeem_points": 200,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["earn_per_byn"] == 10
    assert saved.json()["settings"]["max_redeem_percent"] == 50

    history = client.get(
        f"/api/admin/loyalty/accounts/{row['id']}/transactions", headers=staff
    )
    assert history.status_code == 200
    kinds = {item["kind"] for item in history.json()["items"]}
    assert {"earn", "adjust", "redeem", "refund"} <= kinds
