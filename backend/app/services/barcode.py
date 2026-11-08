"""Штрихкоды EAN-13: генерация, проверка, поиск и бэкфилл товаров."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Product


# Внутренний диапазон EAN-13 для товаров платформы: 20xxxxxxxxxx.
PREFIX = "20"


def check_digit(base12: str) -> str:
    """Контрольная цифра EAN-13 для первых 12 цифр."""
    if len(base12) != 12 or not base12.isdigit():
        raise ValueError("Нужно 12 цифр")
    total = 0
    for index, char in enumerate(base12):
        total += int(char) * (3 if index % 2 else 1)
    return str((10 - total % 10) % 10)


def is_valid(code: str | None) -> bool:
    value = (code or "").strip()
    if len(value) != 13 or not value.isdigit():
        return False
    return check_digit(value[:12]) == value[12]


def generate(product_id: int) -> str:
    """Внутренний EAN-13 на основе id товара: 20 + 10 цифр id + контрольная."""
    base = f"{PREFIX}{int(product_id):010d}"
    if len(base) > 12:
        base = base[-12:]
    return base + check_digit(base)


def normalize(code: str | None) -> str:
    """Приводит введённый код к EAN-13 или объясняет, что не так."""
    value = "".join(char for char in (code or "") if char.isdigit())
    if not value:
        raise HTTPException(status_code=400, detail="Укажите штрихкод")
    if len(value) != 13:
        raise HTTPException(status_code=400, detail="Штрихкод EAN-13 должен содержать 13 цифр")
    if not is_valid(value):
        raise HTTPException(status_code=400, detail="Неверная контрольная сумма штрихкода")
    return value


def _duplicate(db: Session, code: str, product_id: int | None) -> Product | None:
    stmt = select(Product).where(Product.barcode == code)
    if product_id is not None:
        stmt = stmt.where(Product.id != product_id)
    return db.scalar(stmt)


def assign(db: Session, product: Product, code: str | None = None) -> str:
    """Ставит товару проверенный или автоматически созданный штрихкод."""
    if code:
        value = normalize(code)
        if _duplicate(db, value, product.id):
            raise HTTPException(status_code=400, detail="Этот штрихкод уже занят другим товаром")
        product.barcode = value
        return value

    value = generate(product.id or 0)
    if _duplicate(db, value, product.id):
        value = generate(1_000_000_000 + (product.id or 0))
    product.barcode = value
    return value


def assign_default(db: Session, product: Product) -> str:
    """Создаёт код только если у товара его ещё нет."""
    if product.barcode and is_valid(product.barcode):
        return product.barcode
    return assign(db, product)


def lookup(db: Session, code: str | None) -> Product | None:
    """Ищет товар по штрихкоду. Принимает код с пробелами и разделителями."""
    raw = (code or "").strip()
    digits = "".join(char for char in raw if char.isdigit())
    if not digits:
        return None
    clauses = [Product.barcode == digits]
    if len(digits) == 13:
        clauses.append(Product.barcode == digits[-12:])
    if raw != digits:
        clauses.append(Product.barcode == raw)
    return db.scalar(select(Product).where(or_(*clauses)))


def backfill(db: Session) -> int:
    """Создаёт EAN-13 всем товарам без корректного кода. Возвращает число."""
    rows = db.scalars(
        select(Product)
        .where(or_(Product.barcode.is_(None), Product.barcode == ""))
        .order_by(Product.id)
    ).all()
    updated = 0
    for product in rows:
        assign_default(db, product)
        updated += 1
    return updated


def label_payload(product: Product) -> dict:
    """Данные для печати этикетки: код, название, цена и единица."""
    from app.serializers import product_admin_payload

    data = product_admin_payload(product)
    return {
        "id": product.id,
        "title": product.title,
        "barcode": product.barcode,
        "price": data["price"],
        "final_price": data["final_price"],
        "discount_percent": data["discount_percent"],
        "unit": product.unit,
        "weight_note": product.weight_note,
        "category_title": data.get("category_title"),
    }
