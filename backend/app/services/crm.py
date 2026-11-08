"""CRM: карточка клиента, заметки, метки и сегменты базы."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ORDER_CANCELLED,
    ORDER_REJECTED,
    CustomerNote,
    CustomerTag,
    LoyaltyAccount,
    Order,
)
from app.security import format_phone, normalize_phone
from app.services.campaigns import (
    SEGMENTS,
    AudienceFilters,
    Customer,
    _collect,
    _matches,
)
from app.services.loyalty import level_info


def _phone_index(customers: list[Customer]) -> dict[str, Customer]:
    index: dict[str, Customer] = {}
    for customer in customers:
        if customer.key:
            index[customer.key] = customer
        if customer.phone:
            index[customer.phone] = customer
    return index


def _tags(db: Session) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in db.scalars(select(CustomerTag).order_by(CustomerTag.created_at)).all():
        result.setdefault(row.phone, []).append(row.tag)
    return result


def _notes_count(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in db.scalars(select(CustomerNote)).all():
        counts[row.phone] = counts.get(row.phone, 0) + 1
    return counts


def _loyalty(db: Session) -> dict[str, LoyaltyAccount]:
    return {row.phone: row for row in db.scalars(select(LoyaltyAccount)).all()}


def _segments(customer: Customer) -> list[str]:
    return [
        segment.code
        for segment in SEGMENTS
        if segment.code != "all" and _matches(customer, segment.code, AudienceFilters())
    ]


def _serialize(
    customer: Customer,
    tags: dict[str, list[str]],
    notes: dict[str, int],
    loyalty: dict[str, LoyaltyAccount],
) -> dict:
    account = loyalty.get(customer.phone)
    avg = (customer.spent / customer.orders) if customer.orders else Decimal("0")
    data = {
        "key": customer.key,
        "user_id": customer.user_id,
        "name": customer.name or "Клиент",
        "phone": format_phone(customer.phone) if customer.phone else "",
        "phone_raw": customer.phone,
        "email": customer.email,
        "consent": customer.consent,
        "registered": customer.user_id is not None,
        "orders": customer.orders,
        "spent": float(customer.spent),
        "avg_check": float(avg),
        "first_order": customer.first_order,
        "last_order": customer.last_order,
        "registered_at": customer.registered_at,
        "tags": tags.get(customer.phone, []),
        "notes_count": notes.get(customer.phone, 0),
        "segments": _segments(customer),
        "loyalty": (
            {
                "balance": account.balance,
                "level": account.level,
                "level_info": level_info(account.earned_total),
            }
            if account and customer.phone
            else None
        ),
    }
    return data


def _customer_orders(db: Session, customer: Customer) -> list[Order]:
    stmt = select(Order)
    if customer.user_id:
        stmt = stmt.where(Order.user_id == customer.user_id)
    elif customer.phone:
        stmt = stmt.where(Order.phone == customer.phone)
    else:
        return []
    return db.scalars(stmt.order_by(Order.created_at.desc()).limit(100)).all()


def _notes(db: Session, phone: str) -> list[CustomerNote]:
    if not phone:
        return []
    return db.scalars(
        select(CustomerNote)
        .where(CustomerNote.phone == phone)
        .order_by(CustomerNote.created_at.desc(), CustomerNote.id.desc())
        .limit(100)
    ).all()


def note_payload(row: CustomerNote) -> dict:
    return {
        "id": row.id,
        "body": row.body,
        "author": row.author,
        "created_at": row.created_at,
    }


def summary(db: Session) -> dict:
    customers = _collect(db)
    consent = [item for item in customers if item.consent]
    revenue = sum((item.spent for item in consent), Decimal("0"))
    counts = {}
    for segment in SEGMENTS:
        counts[segment.code] = sum(
            1 for item in customers if _matches(item, segment.code, AudienceFilters())
        )
    return {
        "customers": len(customers),
        "consent": len(consent),
        "revenue": float(revenue),
        "avg_check": float(revenue / counts.get("with_orders", 0)) if counts.get("with_orders") else 0,
        "segments": counts,
    }


def _find(db: Session, key: str) -> Customer:
    customers = _collect(db)
    index = _phone_index(customers)
    customer = index.get(key)
    if customer is None:
        normalized = key
        try:
            normalized = normalize_phone(key)
        except ValueError:
            pass
        customer = index.get(normalized)
    if customer is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return customer


def list_customers(
    db: Session,
    search: str = "",
    segment: str = "all",
    limit: int = 200,
) -> dict:
    customers = _collect(db)
    tags = _tags(db)
    notes = _notes_count(db)
    loyalty = _loyalty(db)
    query = search.strip().lower()

    rows: list[dict] = []
    for customer in customers:
        if query:
            haystack = " ".join(
                (customer.name, customer.phone, customer.email, customer.key)
            ).lower()
            if query not in haystack:
                continue
        if segment != "all":
            if segment not in {item.code for item in SEGMENTS}:
                raise HTTPException(status_code=422, detail="Неизвестный сегмент")
            if not _matches(customer, segment, AudienceFilters()):
                continue
        rows.append(_serialize(customer, tags, notes, loyalty))
    rows.sort(key=lambda item: (-item["spent"], -item["orders"], item["name"].lower()))
    return {
        "items": rows[:limit],
        "total": len(rows),
        "summary": summary(db),
        "segments": [
            {
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "count": sum(
                    1
                    for customer in customers
                    if _matches(customer, item.code, AudienceFilters())
                ),
            }
            for item in SEGMENTS
        ],
    }


def detail(db: Session, key: str) -> dict:
    customer = _find(db, key)
    tags = _tags(db)
    notes = _notes_count(db)
    loyalty = _loyalty(db)
    data = _serialize(customer, tags, notes, loyalty)
    data["order_list"] = [
        {
            "id": order.id,
            "number": order.number,
            "status": order.status,
            "total_amount": float(order.total_amount or 0),
            "items_count": order.items_count,
            "pickup_date": order.pickup_date,
            "created_at": order.created_at,
        }
        for order in _customer_orders(db, customer)
    ]
    data["notes"] = [note_payload(row) for row in _notes(db, customer.phone)]
    data["all_orders"] = sum(
        1
        for order in _customer_orders(db, customer)
        if order.status not in (ORDER_CANCELLED, ORDER_REJECTED)
    )
    return data


def add_note(db: Session, key: str, body: str, author: str) -> CustomerNote:
    customer = _find(db, key)
    if not customer.phone:
        raise HTTPException(status_code=400, detail="У клиента нет телефона")
    note = CustomerNote(
        phone=customer.phone,
        user_id=customer.user_id,
        body=body.strip()[:2000],
        author=author[:120],
    )
    db.add(note)
    db.flush()
    return note


def delete_note(db: Session, note_id: int) -> None:
    note = db.get(CustomerNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    db.delete(note)


def add_tag(db: Session, key: str, tag: str) -> CustomerTag:
    customer = _find(db, key)
    if not customer.phone:
        raise HTTPException(status_code=400, detail="У клиента нет телефона")
    clean = " ".join(tag.strip().split())[:40]
    if not clean:
        raise HTTPException(status_code=422, detail="Укажите метку")
    existing = db.scalar(
        select(CustomerTag).where(
            CustomerTag.phone == customer.phone,
            CustomerTag.tag == clean,
        )
    )
    if existing:
        return existing
    row = CustomerTag(phone=customer.phone, tag=clean)
    db.add(row)
    db.flush()
    return row


def delete_tag(db: Session, key: str, tag: str) -> None:
    customer = _find(db, key)
    row = db.scalar(
        select(CustomerTag).where(
            CustomerTag.phone == customer.phone,
            CustomerTag.tag == tag,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Метка не найдена")
    db.delete(row)
