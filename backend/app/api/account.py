import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import ORDER_CANCELLED, AuditLog, Order, PhoneVerification, User
from app.schemas import AccountDeleteIn, OrderOut
from app.security import hash_password, verify_password
from app.serializers import order_payload
from app.services import loyalty
from app.services.orders import cancel_by_customer


router = APIRouter(prefix="/account", tags=["Личный кабинет"])


@router.get("/summary", summary="Сводка по аккаунту")
def account_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders_total = db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id)) or 0
    upcoming = db.scalars(
        select(Order)
        .where(Order.user_id == user.id, Order.status.in_(("new", "confirmed", "ready")))
        .order_by(Order.pickup_date, Order.pickup_time)
        .limit(5)
    ).all()
    spent = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.user_id == user.id, Order.status == "completed"
        )
    ) or 0
    return {
        "orders_total": int(orders_total),
        "upcoming": [order_payload(o) for o in upcoming],
        "spent_total": float(spent),
        "bonus_note": "Оплата и получение — в магазине. Доставка не осуществляется.",
    }


@router.get("/loyalty", summary="Бонусный счёт покупателя")
def my_loyalty(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = loyalty.public_payload(db, user)
    db.commit()
    return payload


@router.get("/orders", summary="История моих заказов")
def my_orders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    total = db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id)) or 0
    rows = db.scalars(stmt.offset(offset).limit(limit)).unique().all()
    return {"items": [order_payload(o) for o in rows], "total": int(total), "limit": limit, "offset": offset}


@router.get("/orders/{number}", response_model=OrderOut, summary="Детали моего заказа")
def my_order(number: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.number == number, Order.user_id == user.id))
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order_payload(order)


@router.post("/orders/{number}/cancel", response_model=OrderOut, summary="Отменить заказ")
def cancel_order(number: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.number == number, Order.user_id == user.id))
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    order = cancel_by_customer(db, order)
    return order_payload(order)


@router.post("/delete", summary="Удалить аккаунт и обезличить данные")
def delete_account(
    payload: AccountDeleteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Удаляет профиль и обезличивает связанные заказы.

    Суммы, состав заказов и даты сохраняются для бухгалтерского учёта,
    но имя, телефон и комментарии покупателя удаляются безвозвратно.
    """
    if payload.confirmation.strip().upper() != "УДАЛИТЬ":
        raise HTTPException(status_code=400, detail="Для подтверждения введите слово УДАЛИТЬ")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный пароль")

    phone = user.phone
    db.execute(
        update(Order)
        .where(or_(Order.user_id == user.id, Order.phone == phone))
        .values(
            user_id=None,
            customer_name="Удалённый покупатель",
            phone="",
            comment="",
            admin_comment="",
        )
    )
    db.execute(
        update(AuditLog)
        .where(or_(AuditLog.user_id == user.id, AuditLog.actor == phone))
        .values(user_id=None, actor="deleted")
    )
    db.execute(delete(PhoneVerification).where(PhoneVerification.phone == phone))

    user.is_active = False
    user.is_phone_verified = False
    user.full_name = "Пользователь удалён"
    user.email = None
    user.consent_personal_data = False
    user.password_hash = hash_password(uuid.uuid4().hex)
    user.phone = f"del-{user.id}-{uuid.uuid4().hex[:8]}"[:20]
    db.commit()
    return {
        "ok": True,
        "message": "Аккаунт удалён, персональные данные обезличены. Сведения о заказах сохранены в объёме, требуемом законодательством.",
    }
