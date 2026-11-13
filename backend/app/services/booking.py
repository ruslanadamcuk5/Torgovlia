"""Универсальная онлайн-запись: специалисты, слоты и записи.

Модель не привязана к категории бизнеса. Парикмахер, массажист, репетитор,
автосервис и клиника используют один и тот же расчёт:

- рабочие часы заведения берутся из настроек сайта;
- у специалиста может быть свой недельный график и дни отсутствия;
- длительность и буфер задаются у услуги (Product.kind = service);
- занятость проверяется по активным записям, поэтому двойная запись
  невозможна даже при одновременных запросах;
- если специалистов нет, работает запись по вместимости услуги.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    APPOINTMENT_ACTIVE,
    APPOINTMENT_CANCELLED,
    APPOINTMENT_COMPLETED,
    APPOINTMENT_CONFIRMED,
    APPOINTMENT_NEW,
    APPOINTMENT_NO_SHOW,
    APPOINTMENT_STATUSES,
    PRODUCT_KIND_SERVICE,
    Appointment,
    Product,
    Specialist,
    utcnow,
)
from app.schemas import BookingCreateIn
from app.serializers import appointment_payload, specialist_payload
from app.services.audit import audit
from app.services.settings import get_settings_model
from app.tenancy import current_tenant, tenant_get
from app.utils import local_now, local_today, money


LOCAL_OFFSET = timedelta(hours=3)
DEFAULT_DURATION = 30
MAX_DURATION = 720


# ─────────────────────────── Время ───────────────────────────

def parse_clock(value: str) -> time:
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Некорректное время") from exc


def local_to_utc(value: datetime) -> datetime:
    """Локальное время Беларуси (UTC+3) → aware UTC."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return (value - LOCAL_OFFSET).replace(tzinfo=timezone.utc)


def utc_to_local(value: datetime) -> datetime:
    """Aware UTC → локальное naive-время для расчётов и подписей."""
    return (value.astimezone(timezone.utc) + LOCAL_OFFSET).replace(tzinfo=None)


def _hours_for(conf, weekday: int) -> dict | None:
    for day in conf.working_hours:
        if int(day.weekday) == weekday:
            if day.closed:
                return None
            return {"open": day.open, "close": day.close, "closed": False}
    return None


def _specialist_hours(specialist: Specialist | None, weekday: int) -> dict | None:
    """График специалиста; пустой список означает график заведения."""
    if not specialist:
        return None
    raw = specialist.working_hours or []
    if not raw:
        return None
    for item in raw:
        try:
            day_index = int(item.get("weekday", -1))
        except (AttributeError, TypeError, ValueError):
            continue
        if day_index != weekday:
            continue
        if item.get("closed"):
            return None
        return {
            "open": item.get("open") or "09:00",
            "close": item.get("close") or "18:00",
            "closed": False,
        }
    return None


def _specialist_day_off(specialist: Specialist | None, target: date) -> bool:
    if not specialist:
        return False
    return target.isoformat() in set(specialist.time_off or [])


def service_duration(product: Product) -> int:
    value = int(product.duration_minutes or 0)
    if value <= 0:
        return DEFAULT_DURATION
    return max(5, min(MAX_DURATION, value))


def _buffer(product: Product) -> int:
    return max(0, min(180, int(product.buffer_minutes or 0)))


def _capacity(product: Product) -> int:
    return max(1, min(100, int(product.capacity or 1)))


# ─────────────────────────── Специалисты ───────────────────────────

def specialists_for(
    db: Session, product: Product | None = None, active_only: bool = True
) -> list[Specialist]:
    stmt = select(Specialist)
    if active_only:
        stmt = stmt.where(Specialist.is_active.is_(True))
    rows = db.scalars(stmt.order_by(Specialist.sort_order, Specialist.name)).all()
    if product is None:
        return list(rows)
    return [
        row
        for row in rows
        if not (row.service_ids or []) or product.id in (row.service_ids or [])
    ]


def _services_brief(db: Session, specialist: Specialist) -> list[dict]:
    ids = [int(item) for item in (specialist.service_ids or []) if str(item).isdigit()]
    if not ids:
        return []
    rows = db.scalars(select(Product).where(Product.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    result: list[dict] = []
    for product_id in ids:
        product = by_id.get(product_id)
        if not product:
            continue
        result.append(
            {
                "id": product.id,
                "slug": product.slug,
                "title": product.title,
                "duration_minutes": service_duration(product),
                "price": float(
                    money(
                        (product.price or 0)
                        * (100 - max(0, min(95, int(product.discount_percent or 0))))
                        / 100
                    )
                ),
            }
        )
    return result


def specialist_detail(db: Session, specialist: Specialist) -> dict:
    return specialist_payload(specialist, _services_brief(db, specialist))


# ─────────────────────────── Слоты ───────────────────────────

def _day_bounds(target: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target, time.min)
    end_local = datetime.combine(target + timedelta(days=1), time.min)
    return local_to_utc(start_local), local_to_utc(end_local)


def _active_appointments(
    db: Session, target: date, exclude_id: int | None = None
) -> list[Appointment]:
    start_utc, end_utc = _day_bounds(target)
    query = select(Appointment).where(
        Appointment.status.in_(APPOINTMENT_ACTIVE),
        Appointment.starts_at < end_utc,
        Appointment.ends_at > start_utc,
    )
    if exclude_id is not None:
        # Перенос: запись не должна блокировать саму себя.
        query = query.where(Appointment.id != exclude_id)
    return list(db.scalars(query).all())


def _overlaps(
    rows: list[Appointment],
    start: datetime,
    end: datetime,
    *,
    specialist_id: int | None = None,
    product_id: int | None = None,
) -> int:
    count = 0
    for row in rows:
        if specialist_id is not None and row.specialist_id != specialist_id:
            continue
        if specialist_id is None and product_id is not None and row.product_id != product_id:
            continue
        blocked_end = row.ends_at + timedelta(minutes=max(0, int(row.buffer_minutes or 0)))
        if row.starts_at < end and blocked_end > start:
            count += 1
    return count


def _slot_start_times(conf, specialists: list[Specialist], weekday: int) -> list[str]:
    """Кандидаты начала: объединение часов заведения и графиков специалистов."""
    opens: list[str] = []
    closes: list[str] = []
    tenant_hours = _hours_for(conf, weekday)
    if tenant_hours:
        opens.append(tenant_hours["open"])
        closes.append(tenant_hours["close"])
    for specialist in specialists:
        custom = _specialist_hours(specialist, weekday)
        if custom:
            opens.append(custom["open"])
            closes.append(custom["close"])
    if not opens:
        return []
    start = min(parse_clock(value) for value in opens)
    end = max(parse_clock(value) for value in closes)
    step = max(5, min(120, int(conf.slot_step_minutes or 30)))
    result: list[str] = []
    current = datetime.combine(date.today(), start)
    limit = datetime.combine(date.today(), end)
    while current < limit:
        result.append(current.strftime("%H:%M"))
        current += timedelta(minutes=step)
    return result


def booking_slots(
    db: Session,
    product: Product,
    target: date,
    specialist_id: int | None = None,
    exclude_id: int | None = None,
) -> dict:
    """Свободные окна на дату с учётом графика, длительности и занятости."""
    conf = get_settings_model(db)
    today = local_today()
    days_ahead = max(1, min(365, int(conf.booking_days_ahead or 7)))
    max_date = today + timedelta(days=days_ahead)

    eligible = specialists_for(db, product)
    if specialist_id is not None:
        eligible = [row for row in eligible if row.id == specialist_id]
        if not eligible:
            raise HTTPException(
                status_code=404, detail="Специалист не найден или не оказывает эту услугу"
            )

    if target < today:
        return {
            "date": target,
            "is_open": False,
            "slots": [],
            "specialists": [],
            "message": "Дата уже прошла",
        }
    if target > max_date:
        return {
            "date": target,
            "is_open": False,
            "slots": [],
            "specialists": [],
            "message": f"Запись открыта на {days_ahead} дней вперёд",
        }

    weekday = target.weekday()
    tenant_hours = _hours_for(conf, weekday)
    working = [s for s in eligible if not _specialist_day_off(s, target)]
    custom = [s for s in working if _specialist_hours(s, weekday)]
    if not tenant_hours and not custom:
        return {
            "date": target,
            "is_open": False,
            "slots": [],
            "specialists": [{"id": s.id, "slug": s.slug, "name": s.name, "role": s.role or "", "photo_url": s.photo_url} for s in working],
            "message": "В этот день мы не работаем",
        }

    duration = service_duration(product)
    buffer = _buffer(product)
    capacity = _capacity(product)
    starts = _slot_start_times(conf, working, weekday)
    now_local = local_now().replace(tzinfo=None)
    earliest = now_local + timedelta(minutes=max(0, int(conf.lead_time_minutes or 0)))
    appointments = _active_appointments(db, target, exclude_id)

    slots: list[dict] = []
    for text in starts:
        start_local = datetime.combine(target, parse_clock(text))
        end_local = start_local + timedelta(minutes=duration)
        blocked_end = end_local + timedelta(minutes=buffer)
        start_utc = local_to_utc(start_local)
        end_utc = local_to_utc(blocked_end)

        free_ids: list[int] = []
        too_early = start_local < earliest
        for specialist in working:
            hours = _specialist_hours(specialist, weekday) or _hours_for(conf, weekday)
            if not hours:
                continue
            open_time = parse_clock(hours["open"])
            close_time = parse_clock(hours["close"])
            if (
                start_local < datetime.combine(target, open_time)
                or blocked_end > datetime.combine(target, close_time)
            ):
                continue
            used = _overlaps(
                appointments, start_utc, end_utc, specialist_id=specialist.id
            )
            if used == 0:
                free_ids.append(specialist.id)

        if working:
            available = bool(free_ids) and not too_early
            capacity_left = len(free_ids)
        else:
            used = _overlaps(
                appointments, start_utc, end_utc, product_id=product.id
            )
            capacity_left = max(0, capacity - used)
            available = capacity_left > 0 and not too_early

        slots.append(
            {
                "time": text,
                "start": start_utc,
                "end": local_to_utc(end_local),
                "available": available,
                "specialist_ids": free_ids if working else [],
                "capacity_left": capacity_left,
            }
        )

    available_count = sum(1 for slot in slots if slot["available"])
    message = ""
    if not available_count:
        message = "Свободных окон нет — выберите другую дату"
    return {
        "date": target,
        "is_open": True,
        "slots": slots,
        "specialists": [
            {
                "id": row.id,
                "slug": row.slug,
                "name": row.name,
                "role": row.role or "",
                "photo_url": row.photo_url,
            }
            for row in working
        ],
        "message": message,
    }


def booking_days(
    db: Session,
    product: Product,
    specialist_id: int | None = None,
    days: int = 21,
) -> dict:
    conf = get_settings_model(db)
    days = max(1, min(60, days))
    today = local_today()
    result: list[dict] = []
    labels = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    for offset in range(days):
        target = today + timedelta(days=offset)
        data = booking_slots(db, product, target, specialist_id)
        result.append(
            {
                "date": target,
                "is_open": bool(data["is_open"]),
                "slots_available": sum(1 for slot in data["slots"] if slot["available"]),
                "label": labels[target.weekday()],
            }
        )
    return {"days": result, "message": ""}


# ─────────────────────────── Записи ───────────────────────────

def _number(db: Session) -> str:
    for _ in range(12):
        candidate = f"Z{today_stamp()}-{secrets.randbelow(9000) + 1000}"
        exists = db.scalar(
            select(Appointment.id).where(Appointment.number == candidate)
        )
        if not exists:
            return candidate
    return f"Z{today_stamp()}-{secrets.token_hex(3).upper()}"


def today_stamp() -> str:
    return local_today().strftime("%y%m%d")


def _ensure_slot(
    db: Session,
    product: Product,
    start_utc: datetime,
    specialist_id: int | None,
    exclude_id: int | None = None,
) -> int | None:
    """Проверяет окно и возвращает id свободного специалиста (если он нужен)."""
    start_local = utc_to_local(start_utc)
    target = start_local.date()
    data = booking_slots(db, product, target, specialist_id, exclude_id)
    if not data["is_open"]:
        raise HTTPException(status_code=409, detail=data.get("message") or "День закрыт")
    clock = start_local.strftime("%H:%M")
    slot = next((item for item in data["slots"] if item["time"] == clock), None)
    if not slot or not slot["available"]:
        raise HTTPException(
            status_code=409,
            detail="Это время уже занято. Выберите другое окно.",
        )
    if specialist_id is not None:
        return specialist_id
    ids = slot.get("specialist_ids") or []
    return int(ids[0]) if ids else None


def _snapshot(product: Product) -> str:
    return product.title


def create_appointment(
    db: Session,
    payload: BookingCreateIn,
    *,
    actor: str = "",
    user_id: int | None = None,
    status: str = APPOINTMENT_NEW,
) -> Appointment:
    product = tenant_get(db, Product, payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    specialist_id = payload.specialist_id
    specialist: Specialist | None = None
    if specialist_id is not None:
        specialist = tenant_get(db, Specialist, specialist_id)
        if not specialist or not specialist.is_active:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        allowed = {row.id for row in specialists_for(db, product)}
        if specialist.id not in allowed:
            raise HTTPException(
                status_code=422, detail="Специалист не оказывает эту услугу"
            )

    start_utc = local_to_utc(payload.starts_at)
    if start_utc <= utcnow():
        raise HTTPException(status_code=422, detail="Нельзя записаться на прошедшее время")

    assigned = _ensure_slot(db, product, start_utc, specialist_id)
    if specialist is None and assigned is not None:
        specialist = tenant_get(db, Specialist, assigned)
        specialist_id = assigned

    duration = service_duration(product)
    end_utc = start_utc + timedelta(minutes=duration)
    price = money(
        (product.price or 0)
        * (100 - max(0, min(95, int(product.discount_percent or 0))))
        / 100
    )
    if status not in APPOINTMENT_STATUSES:
        status = APPOINTMENT_NEW

    appointment = Appointment(
        number=_number(db),
        user_id=user_id,
        product_id=product.id,
        specialist_id=specialist.id if specialist else None,
        service_title=_snapshot(product),
        specialist_name=specialist.name if specialist else "",
        customer_name=payload.customer_name.strip(),
        phone=payload.phone.strip(),
        email=(payload.email or "").strip(),
        starts_at=start_utc,
        ends_at=end_utc,
        duration_minutes=duration,
        buffer_minutes=_buffer(product),
        price=price,
        status=status,
        comment=(payload.comment or "").strip(),
        source=payload.source,
        status_history=[
            {
                "status": status,
                "at": utcnow().isoformat(),
                "actor": actor or "site",
            }
        ],
    )
    db.add(appointment)
    db.flush()
    audit(
        db,
        "appointment.create",
        actor=actor or payload.phone,
        user_id=user_id,
        entity="appointment",
        entity_id=str(appointment.id),
        details={
            "number": appointment.number,
            "service": appointment.service_title,
            "specialist": appointment.specialist_name,
            "starts_at": start_utc.isoformat(),
        },
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(
    db: Session,
    appointment: Appointment,
    starts_at: datetime,
    *,
    specialist_id: int | None = None,
    keep_specialist: bool = True,
    actor: str = "",
) -> Appointment:
    """Переносит активную запись на свободное окно с проверкой доступности."""
    if appointment.status not in APPOINTMENT_ACTIVE:
        raise HTTPException(status_code=409, detail="Эту запись уже нельзя перенести")

    product = tenant_get(db, Product, appointment.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Услуга больше недоступна")

    if keep_specialist and specialist_id is None:
        specialist_id = appointment.specialist_id

    specialist: Specialist | None = None
    if specialist_id is not None:
        specialist = tenant_get(db, Specialist, specialist_id)
        if not specialist or not specialist.is_active:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        allowed = {row.id for row in specialists_for(db, product)}
        if specialist.id not in allowed:
            raise HTTPException(
                status_code=422, detail="Специалист не оказывает эту услугу"
            )

    start_utc = starts_at if starts_at.tzinfo else local_to_utc(starts_at)
    start_utc = start_utc.astimezone(timezone.utc)
    if start_utc <= utcnow():
        raise HTTPException(status_code=422, detail="Нельзя перенести запись на прошедшее время")

    assigned = _ensure_slot(
        db, product, start_utc, specialist_id, exclude_id=appointment.id
    )
    if specialist is None and assigned is not None:
        specialist = tenant_get(db, Specialist, assigned)

    duration = service_duration(product)
    previous_start = appointment.starts_at
    appointment.starts_at = start_utc
    appointment.ends_at = start_utc + timedelta(minutes=duration)
    appointment.duration_minutes = duration
    appointment.buffer_minutes = _buffer(product)
    appointment.price = money(
        (product.price or 0)
        * (100 - max(0, min(95, int(product.discount_percent or 0))))
        / 100
    )
    if specialist is not None:
        appointment.specialist_id = specialist.id
        appointment.specialist_name = specialist.name
    # Новое время — новое напоминание.
    appointment.reminder_sent_at = None
    appointment.status_history = list(appointment.status_history or []) + [
        {
            "status": appointment.status,
            "at": utcnow().isoformat(),
            "actor": actor or "client",
            "action": "reschedule",
            "from": previous_start.isoformat(),
            "to": start_utc.isoformat(),
        }
    ]
    audit(
        db,
        "appointment.reschedule",
        actor=actor or appointment.phone,
        entity="appointment",
        entity_id=str(appointment.id),
        details={
            "number": appointment.number,
            "from": previous_start.isoformat(),
            "to": start_utc.isoformat(),
            "specialist": appointment.specialist_name,
        },
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def find_appointment(db: Session, number: str, phone: str) -> Appointment | None:
    digits = "".join(ch for ch in phone if ch.isdigit())[-9:]
    if len(digits) < 9:
        return None
    rows = db.scalars(
        select(Appointment).where(Appointment.number == number.strip())
    ).all()
    for row in rows:
        if "".join(ch for ch in row.phone if ch.isdigit())[-9:] == digits:
            return row
    return None


def lookup_appointment(db: Session, number: str, phone: str) -> dict:
    appointment = find_appointment(db, number, phone)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return appointment_payload(appointment)


def cancel_appointment(
    db: Session, number: str, phone: str, reason: str = "", actor: str = ""
) -> dict:
    appointment = find_appointment(db, number, phone)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if appointment.status not in APPOINTMENT_ACTIVE:
        raise HTTPException(status_code=409, detail="Эту запись уже нельзя отменить")
    appointment.status = APPOINTMENT_CANCELLED
    if reason:
        appointment.admin_comment = (
            f"{appointment.admin_comment}\n{reason}".strip()
        )
    appointment.status_history = list(appointment.status_history or []) + [
        {"status": APPOINTMENT_CANCELLED, "at": utcnow().isoformat(), "actor": actor or "client"}
    ]
    audit(
        db,
        "appointment.cancel",
        actor=actor or phone,
        entity="appointment",
        entity_id=str(appointment.id),
        details={"number": appointment.number, "reason": reason},
    )
    db.commit()
    db.refresh(appointment)
    return appointment_payload(appointment)


TRANSITIONS: dict[str, set[str]] = {
    APPOINTMENT_NEW: {
        APPOINTMENT_CONFIRMED,
        APPOINTMENT_COMPLETED,
        APPOINTMENT_CANCELLED,
        APPOINTMENT_NO_SHOW,
    },
    APPOINTMENT_CONFIRMED: {
        APPOINTMENT_COMPLETED,
        APPOINTMENT_CANCELLED,
        APPOINTMENT_NO_SHOW,
    },
    APPOINTMENT_COMPLETED: set(),
    APPOINTMENT_CANCELLED: set(),
    APPOINTMENT_NO_SHOW: set(),
}


def change_status(
    db: Session, appointment: Appointment, status: str, actor: str, note: str = ""
) -> Appointment:
    if status not in APPOINTMENT_STATUSES:
        raise HTTPException(status_code=422, detail="Неизвестный статус записи")
    if status == appointment.status:
        return appointment
    if status not in TRANSITIONS.get(appointment.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя перевести запись из «{appointment.status}» в «{status}»",
        )
    appointment.status = status
    if note:
        appointment.admin_comment = f"{appointment.admin_comment}\n{note}".strip()
    appointment.status_history = list(appointment.status_history or []) + [
        {"status": status, "at": utcnow().isoformat(), "actor": actor}
    ]
    audit(
        db,
        "appointment.status",
        actor=actor,
        entity="appointment",
        entity_id=str(appointment.id),
        details={"status": status, "number": appointment.number},
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def upcoming_for_product(
    db: Session, product_id: int, limit: int = 5
) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.product_id == product_id,
                Appointment.status.in_(APPOINTMENT_ACTIVE),
                Appointment.ends_at >= utcnow(),
            )
            .order_by(Appointment.starts_at)
            .limit(limit)
        ).all()
    )


__all__ = [
    "PRODUCT_KIND_SERVICE",
    "booking_days",
    "booking_slots",
    "cancel_appointment",
    "change_status",
    "create_appointment",
    "find_appointment",
    "lookup_appointment",
    "parse_clock",
    "service_duration",
    "specialist_detail",
    "specialists_for",
    "utc_to_local",
]
