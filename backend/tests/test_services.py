"""Универсальный слой услуг: каталог, специалисты и онлайн-запись."""

from __future__ import annotations

import pytest

SERVICE_SIGNUP = {
    "slug": "service-flow",
    "name": "Салон «Тест»",
    "category_preset": "hairdresser",
    "plan_code": "business",
    "owner_phone": "+375291114455",
    "owner_name": "Владелец салона",
    "owner_password": "Service123!",
    "offer_accepted": True,
}


def _headers(token: str, **extra: str) -> dict:
    return {"Authorization": f"Bearer {token}", **extra}


@pytest.fixture(scope="module")
def service_host(client) -> str:
    response = client.post("/api/signup", json=SERVICE_SIGNUP)
    assert response.status_code == 201, response.text
    return response.json()["host"]


def _first_free_slot(client, host: str, product_id: int) -> tuple[str, str, int | None]:
    days = client.get(
        "/api/booking/days",
        headers={"host": host},
        params={"product_id": product_id, "days": 21},
    )
    assert days.status_code == 200, days.text
    day = next((item for item in days.json()["days"] if item["slots_available"] > 0), None)
    assert day, "у сервисного демо-тенанта должно быть свободное время"

    slots = client.get(
        "/api/booking/slots",
        headers={"host": host},
        params={"product_id": product_id, "date": day["date"]},
    )
    assert slots.status_code == 200, slots.text
    slot = next(item for item in slots.json()["slots"] if item["available"])
    specialist_id = slot["specialist_ids"][0] if slot["specialist_ids"] else None
    return day["date"], slot["time"], specialist_id


def test_service_tenant_has_services_and_specialists(client, service_host):
    host = service_host

    site = client.get("/api/site", headers={"host": host})
    assert site.status_code == 200, site.text
    body = site.json()
    assert body["tenant"]["business_type"] == "services"
    assert body["features"]["booking"] is True

    services = client.get("/api/services", headers={"host": host})
    assert services.status_code == 200, services.text
    items = services.json()["items"]
    assert items, "демо-услуги должны создаваться вместе с арендатором"
    assert all(item["kind"] == "service" for item in items)
    assert all(item["duration_minutes"] > 0 for item in items)

    product_id = items[0]["id"]
    specialists = client.get(
        "/api/specialists", headers={"host": host}, params={"service_id": product_id}
    )
    assert specialists.status_code == 200, specialists.text
    people = specialists.json()["items"]
    assert people, "у парикмахерской должны быть специалисты"
    assert all(person["name"] for person in people)
    assert all(
        not person["service_ids"] or product_id in person["service_ids"]
        for person in people
    )


def test_booking_creates_appointment_and_blocks_double_booking(client, service_host):
    host = service_host
    items = client.get("/api/services", headers={"host": host}).json()["items"]
    product_id = items[0]["id"]
    date, time, specialist_id = _first_free_slot(client, host, product_id)

    payload = {
        "product_id": product_id,
        "specialist_id": specialist_id,
        "starts_at": f"{date}T{time}:00",
        "customer_name": "Тестовый Клиент",
        "phone": "+375 (29) 555-44-33",
        "email": "client@example.by",
        "comment": "Первый визит",
        "consent_personal_data": True,
    }
    created = client.post("/api/booking", headers={"host": host}, json=payload)
    assert created.status_code == 200, created.text
    appointment = created.json()
    assert appointment["number"].startswith("Z")
    assert appointment["status"] == "new"
    assert appointment["service_title"] == items[0]["title"]
    assert appointment["phone"] == "+375295554433"

    # Повторная запись на то же время к тому же специалисту невозможна.
    duplicate = client.post(
        "/api/booking",
        headers={"host": host},
        json={**payload, "customer_name": "Второй Клиент", "phone": "+375295554422"},
    )
    assert duplicate.status_code == 409, duplicate.text

    found = client.get(
        f"/api/booking/{appointment['number']}",
        headers={"host": host},
        params={"phone": "+375295554433"},
    )
    assert found.status_code == 200, found.text
    assert found.json()["id"] == appointment["id"]

    cancelled = client.post(
        "/api/booking/cancel",
        headers={"host": host},
        json={"number": appointment["number"], "phone": "+375295554433", "reason": "Планы изменились"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_admin_can_manage_specialists_and_appointments(client, service_host):
    host = service_host
    login = client.post(
        "/api/auth/login",
        headers={"host": host},
        json={
            "phone": SERVICE_SIGNUP["owner_phone"],
            "password": SERVICE_SIGNUP["owner_password"],
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    business = client.get("/api/admin/business", headers=_headers(token, host=host))
    assert business.status_code == 200, business.text
    assert business.json()["business_type"] == "services"

    services = client.get("/api/services", headers={"host": host}).json()["items"]
    specialities = client.get("/api/admin/specialists", headers=_headers(token, host=host))
    assert specialities.status_code == 200, specialities.text
    assert specialities.json()["items"]

    created = client.post(
        "/api/admin/specialists",
        headers=_headers(token, host=host),
        json={
            "name": "Новый мастер",
            "role": "Стилист",
            "service_ids": [services[0]["id"]],
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["slug"]
    assert created.json()["services"][0]["id"] == services[0]["id"]

    date, time, _ = _first_free_slot(client, host, services[1]["id"])
    manual = client.post(
        "/api/admin/appointments",
        headers=_headers(token, host=host),
        json={
            "product_id": services[1]["id"],
            "starts_at": f"{date}T{time}:00",
            "customer_name": "Клиент по телефону",
            "phone": "+375295554411",
            "consent_personal_data": True,
            "status": "confirmed",
        },
    )
    assert manual.status_code == 201, manual.text
    appointment = manual.json()
    assert appointment["source"] == "admin"
    assert appointment["status"] == "confirmed"

    listed = client.get("/api/admin/appointments", headers=_headers(token, host=host))
    assert listed.status_code == 200, listed.text
    numbers = [item["number"] for item in listed.json()["items"]]
    assert appointment["number"] in numbers

    completed = client.patch(
        f"/api/admin/appointments/{appointment['id']}",
        headers=_headers(token, host=host),
        json={"status": "completed", "admin_comment": "Визит состоялся"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
