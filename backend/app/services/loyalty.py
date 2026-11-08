"""Бонусная программа: баллы за полученные заказы, списание и уровни."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    LoyaltyAccount,
    LoyaltySettings,
    LoyaltyTransaction,
    Order,
    User,
)
from app.security import format_phone, normalize_phone
from app.utils import money


LEVELS = (
    ("bronze", "Бронза", 0, Decimal("1.00")),
    ("silver", "Серебро", 1000, Decimal("1.25")),
    ("gold", "Золото", 5000, Decimal("1.50")),
)
LEVEL_BY_CODE = {code: (title, threshold, multiplier) for code, title, threshold, multiplier in LEVELS}

DEFAULTS = {
    "is_active": True,
    "earn_per_byn": 5,
    "point_value": Decimal("0.0100"),
    "max_redeem_percent": 30,
    "min_redeem_points": 100,
}


def get_settings(db: Session) -> LoyaltySettings:
    row = db.scalar(select(LoyaltySettings))
    if row is None:
        row = LoyaltySettings(**DEFAULTS)
        db.add(row)
        db.flush()
    return row


def level_for(earned_total: int) -> str:
    code = LEVELS[0][0]
    for level_code, _title, threshold, _multiplier in LEVELS:
        if earned_total >= threshold:
            code = level_code
    return code


def level_info(earned_total: int) -> dict:
    code = level_for(earned_total)
    index = next(i for i, level in enumerate(LEVELS) if level[0] == code)
    next_level = LEVELS[index + 1] if index + 1 < len(LEVELS) else None
    current = LEVELS[index]
    return {
        "code": code,
        "title": current[1],
        "multiplier": float(current[3]),
        "threshold": current[2],
        "next": (
            {
                "code": next_level[0],
                "title": next_level[1],
                "threshold": next_level[2],
                "multiplier": float(next_level[3]),
                "remaining": max(0, next_level[2] - earned_total),
            }
            if next_level
            else None
        ),
    }


def account_for(
    db: Session,
    phone: str,
    name: str = "",
    user_id: int | None = None,
) -> LoyaltyAccount:
    try:
        normalized = normalize_phone(phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона") from exc
    account = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.phone == normalized))
    if account is None:
        account = LoyaltyAccount(phone=normalized, name=name[:120], user_id=user_id)
        db.add(account)
        db.flush()
    elif name and not account.name:
        account.name = name[:120]
    if user_id and not account.user_id:
        account.user_id = user_id
    return account


def account_for_user(db: Session, user: User) -> LoyaltyAccount:
    account = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.user_id == user.id))
    if account:
        return account
    return account_for(db, user.phone, user.full_name, user.id)


def _transaction(
    db: Session,
    account: LoyaltyAccount,
    kind: str,
    points: int,
    note: str,
    actor: str = "",
    order_id: int | None = None,
) -> LoyaltyTransaction:
    row = LoyaltyTransaction(
        account_id=account.id,
        order_id=order_id,
        kind=kind,
        points=points,
        balance_after=account.balance,
        note=note[:255],
        actor=actor[:120],
    )
    db.add(row)
    return row


def redeem(
    db: Session,
    phone: str,
    user_id: int | None,
    points: int,
    subtotal: Decimal,
) -> tuple[int, Decimal]:
    """Списывает баллы к заказу. Возвращает (баллы, скидка в BYN)."""
    conf = get_settings(db)
    if not conf.is_active:
        raise HTTPException(status_code=400, detail="Бонусная программа выключена")
    if points <= 0:
        return 0, Decimal("0.00")
    account = account_for(db, phone, user_id=user_id)
    if points < conf.min_redeem_points:
        raise HTTPException(
            status_code=400,
            detail=f"Минимум для списания — {conf.min_redeem_points} баллов",
        )
    if points > account.balance:
        raise HTTPException(
            status_code=400,
            detail=f"На счёте только {account.balance} баллов",
        )
    max_discount = money(subtotal * Decimal(conf.max_redeem_percent) / 100)
    max_points = int(max_discount / Decimal(conf.point_value)) if conf.point_value else 0
    allowed = min(account.balance, max_points)
    if points > allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Можно списать не больше {allowed} баллов "
                f"({conf.max_redeem_percent}% суммы заказа)"
            ),
        )
    discount = money(Decimal(points) * Decimal(conf.point_value))
    account.balance -= points
    account.spent_total += points
    _transaction(db, account, "redeem", -points, "Списание при оформлении заказа", actor="client")
    return points, discount


def award_for_order(db: Session, order: Order) -> int:
    """Начисляет баллы за полученный заказ один раз."""
    if order.points_earned:
        return 0
    conf = get_settings(db)
    if not conf.is_active:
        return 0
    goods = Decimal(order.total_amount or 0) - Decimal(order.delivery_fee or 0)
    if goods <= 0:
        return 0
    account = account_for(db, order.phone, order.customer_name, order.user_id)
    code = level_for(account.earned_total)
    multiplier = LEVEL_BY_CODE[code][2]
    points = int(goods * Decimal(conf.earn_per_byn) * multiplier)
    if points <= 0:
        return 0
    account.balance += points
    account.earned_total += points
    account.spent_total = max(0, account.spent_total)
    account.level = level_for(account.earned_total)
    _transaction(
        db,
        account,
        "earn",
        points,
        f"Начисление за заказ {order.number}",
        actor="system",
        order_id=order.id,
    )
    order.points_earned = points
    return points


def refund_for_cancel(db: Session, order: Order, actor: str = "system") -> int:
    """Возвращает списанные баллы при отмене или отклонении заказа."""
    used = int(order.points_used or 0)
    if used <= 0:
        return 0
    account = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.phone == order.phone))
    if account is None and order.user_id:
        account = db.scalar(select(LoyaltyAccount).where(LoyaltyAccount.user_id == order.user_id))
    if account is None:
        return 0
    account.balance += used
    account.spent_total = max(0, account.spent_total - used)
    _transaction(
        db,
        account,
        "refund",
        used,
        f"Возврат за отмену заказа {order.number}",
        actor=actor,
        order_id=order.id,
    )
    order.points_used = 0
    order.points_discount = Decimal("0.00")
    return used


def adjust(db: Session, account: LoyaltyAccount, points: int, note: str, actor: str) -> LoyaltyAccount:
    if points == 0:
        raise HTTPException(status_code=422, detail="Укажите количество баллов")
    if points < 0 and account.balance + points < 0:
        raise HTTPException(status_code=400, detail="Баланс не может стать отрицательным")
    account.balance += points
    if points > 0:
        account.earned_total += points
    else:
        account.spent_total = max(0, account.spent_total - points)
    account.level = level_for(account.earned_total)
    _transaction(db, account, "adjust", points, note or "Ручная корректировка", actor=actor)
    db.flush()
    return account


def serialize_account(account: LoyaltyAccount) -> dict:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "name": account.name or "Покупатель",
        "phone": format_phone(account.phone),
        "phone_raw": account.phone,
        "balance": account.balance,
        "earned_total": account.earned_total,
        "spent_total": account.spent_total,
        "level": account.level,
        "level_info": level_info(account.earned_total),
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def serialize_transaction(row: LoyaltyTransaction, order_number: str = "") -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "points": row.points,
        "balance_after": row.balance_after,
        "note": row.note,
        "order_number": order_number,
        "actor": row.actor,
        "created_at": row.created_at,
    }


def settings_payload(conf: LoyaltySettings) -> dict:
    return {
        "is_active": conf.is_active,
        "earn_per_byn": conf.earn_per_byn,
        "point_value": float(conf.point_value),
        "max_redeem_percent": conf.max_redeem_percent,
        "min_redeem_points": conf.min_redeem_points,
        "levels": [
            {
                "code": code,
                "title": title,
                "threshold": threshold,
                "multiplier": float(multiplier),
            }
            for code, title, threshold, multiplier in LEVELS
        ],
    }


def public_payload(db: Session, user: User) -> dict:
    conf = get_settings(db)
    account = account_for_user(db, user)
    history = db.scalars(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.account_id == account.id)
        .order_by(LoyaltyTransaction.created_at.desc(), LoyaltyTransaction.id.desc())
        .limit(20)
    ).all()
    orders = {
        order.id: order.number
        for order in db.scalars(
            select(Order).where(Order.id.in_([row.order_id for row in history if row.order_id]))
        ).all()
    } if any(row.order_id for row in history) else {}
    return {
        "enabled": bool(conf.is_active),
        "balance": account.balance,
        "level": account.level,
        "level_info": level_info(account.earned_total),
        "earned_total": account.earned_total,
        "spent_total": account.spent_total,
        "settings": settings_payload(conf),
        "transactions": [
            serialize_transaction(row, orders.get(row.order_id or 0, "")) for row in history
        ],
    }


def admin_list(db: Session, search: str = "", limit: int = 100) -> dict:
    conf = get_settings(db)
    stmt = select(LoyaltyAccount).order_by(LoyaltyAccount.balance.desc(), LoyaltyAccount.updated_at.desc())
    if search.strip():
        query = f"%{search.strip()}%"
        stmt = stmt.where(or_(LoyaltyAccount.phone.contains(query), LoyaltyAccount.name.ilike(query)))
    rows = db.scalars(stmt.limit(limit)).all()
    totals = db.execute(
        select(
            func.count(LoyaltyAccount.id),
            func.coalesce(func.sum(LoyaltyAccount.balance), 0),
            func.coalesce(func.sum(LoyaltyAccount.earned_total), 0),
            func.coalesce(func.sum(LoyaltyAccount.spent_total), 0),
        )
    ).one()
    levels = dict(
        db.execute(
            select(LoyaltyAccount.level, func.count(LoyaltyAccount.id)).group_by(LoyaltyAccount.level)
        ).all()
    )
    return {
        "settings": settings_payload(conf),
        "summary": {
            "accounts": int(totals[0] or 0),
            "balance": int(totals[1] or 0),
            "earned": int(totals[2] or 0),
            "spent": int(totals[3] or 0),
            "levels": levels,
        },
        "items": [serialize_account(row) for row in rows],
    }


def account_history(db: Session, account: LoyaltyAccount, limit: int = 100) -> dict:
    rows = db.scalars(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.account_id == account.id)
        .order_by(LoyaltyTransaction.created_at.desc(), LoyaltyTransaction.id.desc())
        .limit(limit)
    ).all()
    order_ids = [row.order_id for row in rows if row.order_id]
    orders = {
        order.id: order.number
        for order in db.scalars(select(Order).where(Order.id.in_(order_ids))).all()
    } if order_ids else {}
    return {
        "account": serialize_account(account),
        "items": [serialize_transaction(row, orders.get(row.order_id or 0, "")) for row in rows],
    }
