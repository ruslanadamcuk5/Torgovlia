"""Аудит изоляции арендаторов (задача 10.2).

Проверяем не только списки, но и доступ по чужому ID: это основной сценарий
утечки, когда объект найден по `id` без фильтра `tenant_id`.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.db import SessionLocal
from app.models import ORDER_NEW, AuditLog, CustomerNote, Order
from app.security import hash_password


STORE_A = {"slug": "odezhda", "phone": "+375291112288", "password": "ChangeMe123!"}
STORE_B = {"slug": "flowers", "phone": "+375291112266", "password": "ChangeMe123!"}

def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (200, 120, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def _platform_token(client) -> str:
    from app.config import settings

    response = client.post(
        "/api/platform/auth/login",
        json={
            "phone": settings.platform_admin_phone,
            "password": settings.platform_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token(client, store: dict) -> str:
    response = client.post(
        "/api/auth/login",
        headers={"host": f"{store['slug']}.localhost"},
        json={"phone": store["phone"], "password": store["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def stores(client):
    platform = _platform_token(client)
    response = client.get(
        "/api/platform/tenants",
        headers={"Authorization": f"Bearer {platform}"},
    )
    assert response.status_code == 200, response.text
    by_slug = {item["slug"]: item for item in response.json()["items"]}
    assert STORE_A["slug"] in by_slug and STORE_B["slug"] in by_slug, "нужны демо-магазины"

    data = {}
    for store in (STORE_A, STORE_B):
        tenant_id = by_slug[store["slug"]]["id"]
        # Тесты API могли выключить сервис у демо-магазина до нас. Включаем
        # нужные сервисы через платформу, чтобы проверка изоляции не зависела
        # от порядка тестов.
        for code in ("gift_certificates", "tasks", "subscriptions"):
            restored = client.patch(
                f"/api/platform/tenants/{tenant_id}/services/{code}",
                headers={"Authorization": f"Bearer {platform}"},
                json={"status": "enabled"},
            )
            assert restored.status_code == 200, restored.text
        token = _admin_token(client, store)
        data[store["slug"]] = {
            **store,
            "id": tenant_id,
            "token": token,
            "host": f"{store['slug']}.localhost",
            "headers": {
                "Authorization": f"Bearer {token}",
                "host": f"{store['slug']}.localhost",
            },
        }
    return data


def _seed_order_and_customer(tenant_id: int, suffix: str) -> tuple[Order, CustomerNote]:
    """Готовим заказ и заметку напрямую в БД, минуя SMS-подтверждение."""
    phone = f"+37529111{int(suffix[:4], 16) % 10000:04d}"
    with SessionLocal() as db:
        order = Order(
            tenant_id=tenant_id,
            number=f"ISO-{suffix.upper()[:8]}",
            customer_name="Клиент изоляции",
            phone=phone,
            pickup_date=date.today(),
            pickup_time="12:00",
            status=ORDER_NEW,
            total_amount=Decimal("25.00"),
            items_count=1,
        )
        note = CustomerNote(
            tenant_id=tenant_id,
            phone=phone,
            body=f"секретная заметка {suffix}",
            author="Тест",
        )
        db.add_all([order, note])
        db.commit()
        db.refresh(order)
        db.refresh(note)
        return order, note


def test_store_tokens_do_not_cross_hosts(client, stores):
    token_a = stores[STORE_A["slug"]]["token"]
    response = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {token_a}", "host": f"{STORE_B['slug']}.localhost"},
    )
    assert response.status_code == 401, response.text


def test_products_are_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    suffix = uuid4().hex[:8]
    slug = f"iso-product-{suffix}"

    created = client.post(
        "/api/admin/products",
        headers=a["headers"],
        json={"title": f"Товар изоляции {suffix}", "slug": slug, "price": 10, "unit": "piece"},
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["id"]

    assert client.get(f"/api/admin/products/{product_id}", headers=b["headers"]).status_code == 404
    assert client.patch(
        f"/api/admin/products/{product_id}", headers=b["headers"], json={"price": 1}
    ).status_code == 404
    assert client.delete(f"/api/admin/products/{product_id}", headers=b["headers"]).status_code == 404

    b_products = client.get("/api/admin/products", headers=b["headers"]).json()
    assert slug not in {item["slug"] for item in b_products.get("items", [])}

    b_public = client.get("/api/products", headers={"host": b["host"]}).json()
    assert slug not in {item["slug"] for item in b_public["items"]}
    a_public = client.get("/api/products", headers={"host": a["host"]}).json()
    assert slug in {item["slug"] for item in a_public["items"]}


def test_orders_and_customer_notes_are_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    suffix = uuid4().hex[:8]
    order, note = _seed_order_and_customer(a["id"], suffix)

    assert client.get(f"/api/admin/orders/{order.id}", headers=b["headers"]).status_code == 404
    assert client.patch(
        f"/api/admin/orders/{order.id}", headers=b["headers"], json={"status": "completed"}
    ).status_code == 404

    b_orders = client.get("/api/admin/orders", headers=b["headers"]).json()
    assert order.number not in {item["number"] for item in b_orders.get("items", [])}

    lookup = client.post(
        "/api/orders/lookup",
        headers={"host": b["host"]},
        json={"number": order.number, "phone": order.phone},
    )
    assert lookup.status_code == 404, lookup.text

    assert client.delete(
        f"/api/admin/crm/notes/{note.id}", headers=b["headers"]
    ).status_code == 404
    detail = client.get(f"/api/admin/crm/customers/{order.phone}", headers=b["headers"])
    assert detail.status_code == 404, detail.text
    b_crm = client.get("/api/admin/crm", headers=b["headers"]).json()
    assert order.phone not in {item["phone"] for item in b_crm.get("items", [])}


def test_gift_certificates_are_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    response = client.post(
        "/api/admin/certificates",
        headers=a["headers"],
        json={"amount": 50, "recipient_name": "Получатель", "activate": True},
    )
    assert response.status_code == 200, response.text
    cert = response.json()
    code = cert["code"]

    b_list = client.get("/api/admin/certificates", headers=b["headers"])
    assert b_list.status_code == 200, b_list.text
    assert code not in {item["code"] for item in b_list.json()["items"]}

    assert client.patch(
        f"/api/admin/certificates/{cert['id']}",
        headers=b["headers"],
        json={"status": "cancelled"},
    ).status_code == 404

    check = client.post(
        "/api/gift-certificates/check",
        headers={"host": b["host"]},
        json={"code": code, "subtotal": 10},
    )
    assert check.status_code == 404, check.text


def test_staff_tasks_are_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    suffix = uuid4().hex[:8]
    created = client.post(
        "/api/admin/tasks",
        headers=a["headers"],
        json={"title": f"Задача изоляции {suffix}", "priority": "high"},
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    b_list = client.get("/api/admin/tasks", headers=b["headers"])
    assert b_list.status_code == 200, b_list.text
    assert task_id not in {item["id"] for item in b_list.json()["items"]}

    assert client.patch(
        f"/api/admin/tasks/{task_id}", headers=b["headers"], json={"status": "done"}
    ).status_code == 404


def test_regular_orders_are_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    suffix = uuid4().hex[:8]
    product = client.post(
        "/api/admin/products",
        headers=a["headers"],
        json={"title": f"Товар подписки {suffix}", "slug": f"iso-sub-{suffix}", "price": 12},
    )
    assert product.status_code == 200, product.text
    created = client.post(
        "/api/admin/subscriptions",
        headers=a["headers"],
        json={
            "customer_name": "Клиент подписки",
            "phone": "+375291119999",
            "interval_days": 14,
            "next_order_date": (date.today() + timedelta(days=14)).isoformat(),
            "items": [{"product_id": product.json()["id"], "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    sub_id = created.json()["id"]

    b_list = client.get("/api/admin/subscriptions", headers=b["headers"])
    assert b_list.status_code == 200, b_list.text
    assert sub_id not in {item["id"] for item in b_list.json()["items"]}

    assert client.patch(
        f"/api/admin/subscriptions/{sub_id}", headers=b["headers"], json={"status": "paused"}
    ).status_code == 404


def test_audit_log_is_tenant_scoped(client, stores):
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    marker = f"iso.audit.{uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(AuditLog(tenant_id=a["id"], actor="Тест", action=marker, entity="test"))
        db.commit()

    b_audit = client.get("/api/admin/audit", headers=b["headers"])
    assert b_audit.status_code == 200, b_audit.text
    assert marker not in {item["action"] for item in b_audit.json()["items"]}

    a_audit = client.get("/api/admin/audit", headers=a["headers"])
    assert marker in {item["action"] for item in a_audit.json()["items"]}


def test_uploads_are_namespaced_by_store(client, stores):
    a = stores[STORE_A["slug"]]
    uploaded = client.post(
        "/api/admin/uploads",
        headers=a["headers"],
        files={"file": ("iso.png", _png(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    url = uploaded.json()["url"]
    assert f"/uploads/{a['slug']}/" in url, url
    served = client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/")


def test_foreign_user_and_certificate_ids_are_not_reusable(client, stores):
    """Даже зная чужой ID, нельзя привязать его к своей сущности."""
    a = stores[STORE_A["slug"]]
    b = stores[STORE_B["slug"]]
    suffix = uuid4().hex[:8]

    with SessionLocal() as db:
        from app.models import User

        foreign_user = User(
            tenant_id=a["id"],
            phone=f"+37529118{int(suffix[:4], 16) % 10000:04d}",
            password_hash=hash_password("Foreign123!"),
            full_name="Чужой сотрудник",
            role="seller",
        )
        db.add(foreign_user)
        db.commit()
        db.refresh(foreign_user)

    response = client.post(
        "/api/admin/tasks",
        headers=b["headers"],
        json={"title": "Задача с чужим исполнителем", "assignee_id": foreign_user.id},
    )
    assert response.status_code in (404, 422), response.text

    cert = client.post(
        "/api/admin/certificates",
        headers=a["headers"],
        json={"amount": 30, "recipient_name": "Получатель", "activate": True},
    )
    assert cert.status_code == 200, cert.text
    cert_id = cert.json()["id"]
    assert client.patch(
        f"/api/admin/certificates/{cert_id}", headers=b["headers"], json={"note": "чужая правка"}
    ).status_code == 404
