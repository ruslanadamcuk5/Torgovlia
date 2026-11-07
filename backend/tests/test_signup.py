"""Публичная регистрация магазина: каталог, создание, оплата первого счёта."""

from app.config import settings


SIGNUP = {
    "slug": "signup-flow",
    "name": "Магазин самообслуживания",
    "category_preset": "bakery",
    "plan_code": "pro",
    "owner_phone": "+375291113300",
    "owner_name": "Новый владелец",
    "owner_password": "Signup123!",
    "offer_accepted": True,
}


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


def _headers(token: str, **extra: str) -> dict:
    return {"Authorization": f"Bearer {token}", **extra}


def test_signup_catalog_is_public(client):
    response = client.get("/api/signup/catalog")
    assert response.status_code == 200, response.text
    data = response.json()
    assert [plan["code"] for plan in data["plans"]] == ["start", "business", "pro"]
    codes = {item["code"] for item in data["categories"]}
    assert {"fish", "meat", "flowers", "grocery", "bakery", "other"} <= codes


def test_signup_creates_onboarding_tenant_and_invoice(client):
    response = client.post("/api/signup", json=SIGNUP)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["slug"] == "signup-flow"
    assert data["status"] == "onboarding"
    assert data["plan_code"] == "pro"
    assert data["price_month"] == 99.0
    assert data["host"] == "signup-flow.localhost"
    assert data["invoice"]["status"] == "open"
    assert data["invoice"]["amount"] == 99.0

    site = client.get("/api/site", headers={"host": data["host"]})
    assert site.status_code == 200, site.text
    assert site.json()["tenant"]["slug"] == "signup-flow"
    assert site.json()["settings"]["brand_name"] == SIGNUP["name"]

    products = client.get("/api/products", headers={"host": data["host"]})
    assert products.status_code == 200
    titles = [item["title"] for item in products.json()["items"]]
    assert "Хлеб бородинский" in titles
    assert "Торт «Медовик»" in titles

    login = client.post(
        "/api/auth/login",
        headers={"host": data["host"]},
        json={"phone": SIGNUP["owner_phone"], "password": SIGNUP["owner_password"]},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["role"] == "admin"

    token = _platform_token(client)
    listed = client.get(
        "/api/platform/tenants", headers=_headers(token), params={"q": "signup-flow"}
    )
    tenant = next(item for item in listed.json()["items"] if item["slug"] == "signup-flow")
    assert tenant["status"] == "onboarding"

    paid = client.post(
        f"/api/platform/invoices/{data['invoice']['id']}/paid", headers=_headers(token)
    )
    assert paid.status_code == 200, paid.text

    tenant_after = client.get(
        f"/api/platform/tenants/{tenant['id']}", headers=_headers(token)
    ).json()
    assert tenant_after["status"] == "active"
    assert tenant_after["plan_code"] == "pro"


def test_signup_rejects_duplicate_and_reserved_slug(client):
    duplicate = client.post("/api/signup", json={**SIGNUP, "owner_phone": "+375291113301"})
    assert duplicate.status_code == 409

    reserved = client.post(
        "/api/signup",
        json={**SIGNUP, "slug": "platform", "owner_phone": "+375291113302"},
    )
    assert reserved.status_code == 409


def test_signup_rejects_weak_password_and_bad_category(client):
    weak = client.post(
        "/api/signup",
        json={**SIGNUP, "slug": "signup-weak", "owner_password": "short", "owner_phone": "+375291113303"},
    )
    assert weak.status_code == 422

    bad_category = client.post(
        "/api/signup",
        json={**SIGNUP, "slug": "signup-badcat", "category_preset": "spaceships", "owner_phone": "+375291113304"},
    )
    assert bad_category.status_code == 422


def test_signup_slug_check(client):
    free = client.get("/api/signup/check-slug", params={"slug": "new-free-shop"})
    assert free.status_code == 200
    assert free.json()["available"] is True

    taken = client.get("/api/signup/check-slug", params={"slug": "signup-flow"})
    assert taken.status_code == 200
    assert taken.json()["available"] is False

    reserved = client.get("/api/signup/check-slug", params={"slug": "platform"})
    assert reserved.json()["available"] is False
