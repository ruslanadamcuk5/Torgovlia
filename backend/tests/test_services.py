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


def test_demo_salon_shows_booking(client):
    headers = {"X-Tenant-Slug": "salon"}
    site = client.get("/api/site", headers=headers)
    assert site.status_code == 200, site.text
    assert site.json()["tenant"]["business_type"] == "services"
    assert site.json()["features"]["booking"] is True

    services = client.get("/api/services", headers=headers)
    assert services.status_code == 200, services.text
    assert services.json()["items"], "демо-салон должен поставляться с услугами"

    specialists = client.get("/api/specialists", headers=headers)
    assert specialists.status_code == 200, specialists.text
    assert specialists.json()["items"], "у демо-салона должны быть специалисты"

    demo = client.get("/api/platform/demo")
    assert demo.status_code == 200, demo.text
    service = demo.json()["service_demo"]
    assert service["slug"] == "salon"
    assert service["booking_url"].endswith("/shop/salon/booking")

    # Доступы из ответа лендинга должны совпадать с настройками и реально
    # пускать владельца в админку салона.
    from app.config import settings

    assert service["phone"] == settings.service_demo_phone
    assert service["password"] == settings.service_demo_password
    login = client.post(
        "/api/auth/login",
        headers=headers,
        json={"phone": service["phone"], "password": service["password"]},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]


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


def test_demo_reset_clears_salon_appointments(client):
    from app.config import settings

    headers = {"X-Tenant-Slug": "salon"}
    items = client.get("/api/services", headers=headers).json()["items"]
    days = client.get(
        "/api/booking/days", headers=headers, params={"product_id": items[0]["id"], "days": 21}
    ).json()["days"]
    day = next(item for item in days if item["slots_available"] > 0)
    slots = client.get(
        "/api/booking/slots",
        headers=headers,
        params={"product_id": items[0]["id"], "date": day["date"]},
    ).json()["slots"]
    slot = next(item for item in slots if item["available"])
    created = client.post(
        "/api/booking",
        headers=headers,
        json={
            "product_id": items[0]["id"],
            "starts_at": f"{day['date']}T{slot['time']}:00",
            "customer_name": "Гость демо",
            "phone": "+375297770011",
            "consent_personal_data": True,
        },
    )
    assert created.status_code == 200, created.text
    number = created.json()["number"]

    login = client.post(
        "/api/platform/auth/login",
        json={"phone": settings.platform_admin_phone, "password": settings.platform_admin_password},
    )
    token = login.json()["access_token"]
    reset = client.post(
        "/api/platform/demo/reset", headers={"Authorization": f"Bearer {token}"}
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["ok"] is True
    assert any(item["slug"] == "salon" for item in reset.json()["tenants"])

    missing = client.get(
        f"/api/booking/{number}", headers=headers, params={"phone": "+375297770011"}
    )
    assert missing.status_code == 404, missing.text
    after = client.get("/api/services", headers=headers).json()["items"]
    assert after, "после сброса демо-салон снова наполнен услугами"


def test_reminders_are_sent_once(client):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Appointment, Product, Tenant
    from app.services import appointment_reminders

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "salon"))
        service = db.scalar(
            select(Product).where(Product.tenant_id == tenant.id, Product.kind == "service")
        )
        now = datetime.now(timezone.utc)
        appointment = Appointment(
            tenant_id=tenant.id,
            number="Z-REMINDER-1",
            product_id=service.id,
            service_title=service.title,
            customer_name="Клиент напоминания",
            phone="+375297770022",
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=3),
            duration_minutes=60,
            status="confirmed",
            source="admin",
            status_history=[],
        )
        db.add(appointment)
        db.commit()

        first = appointment_reminders.send_due(db)
        assert first["sent"] >= 1, first
        db.refresh(appointment)
        assert appointment.reminder_sent_at is not None

        second = appointment_reminders.send_due(db)
        assert second["sent"] == 0, second
    finally:
        db.close()
