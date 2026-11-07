from datetime import date, timedelta


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


def _staff_token(client, phone: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


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
    settings["template"] = "ocean"
    saved = client.put("/api/admin/settings", headers=headers, json=settings)
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["template"] == "ocean"

    site = client.get("/api/site").json()
    assert site["settings"]["template"] == "ocean"
    assert site["theme"]["code"] == "ocean"
    assert site["theme"]["tokens"]["teal"] == ocean["tokens"]["teal"]

    settings["template"] = original
    restored = client.put("/api/admin/settings", headers=headers, json=settings)
    assert restored.status_code == 200, restored.text
    assert client.get("/api/site").json()["settings"]["template"] == original
