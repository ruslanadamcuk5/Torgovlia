"""API регулярных заказов: админка магазина и личный кабинет покупателя."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import SUB_ACTIVE, SUB_CANCELLED, SUB_PAUSED, RegularOrder, User
from app.schemas import (
    SubscriptionAccountPatchIn,
    SubscriptionCreateIn,
    SubscriptionIn,
    SubscriptionPatchIn,
)
from app.services import subscriptions as subscription_service
from app.services.audit import audit


admin_router = APIRouter(prefix="/admin/subscriptions", tags=["Регулярные заказы"])
account_router = APIRouter(prefix="/account/subscriptions", tags=["Регулярные заказы"])


def _actor(user: User) -> str:
    return user.full_name or user.phone


def _payload(db: Session, sub: RegularOrder) -> dict:
    grouped = subscription_service.items_for(db, [sub.id]).get(sub.id, [])
    order = None
    if sub.last_order_id:
        from app.models import Order

        order = db.scalar(select(Order).where(Order.id == sub.last_order_id))
    return subscription_service.payload(db, sub, grouped, order)


@admin_router.get("", summary="Регулярные заказы и сводка")
def subscriptions_list(
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(default=300, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subscription_service.require_enabled(db)
    created = subscription_service.materialize_due(db)
    return {
        "items": subscription_service.list_subscriptions(
            db, status=status, q=q, limit=limit
        ),
        "summary": subscription_service.summary(db),
        "created_now": [
            {"id": order.id, "number": order.number, "total": float(order.total_amount or 0)}
            for order in created
        ],
    }


@admin_router.post("", summary="Создать регулярный заказ")
def subscriptions_create(
    payload: SubscriptionIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = subscription_service.require_enabled(db)
    user_id = payload.user_id
    if user_id is not None:
        owner = db.scalar(select(User).where(User.id == user_id))
        if not owner:
            raise HTTPException(status_code=422, detail="Покупатель не найден")
        user_id = owner.id
    sub = subscription_service.create(
        db,
        tenant_id,
        customer_name=payload.customer_name,
        phone=payload.phone,
        interval_days=payload.interval_days,
        next_order_date=payload.next_order_date,
        items=payload.items,
        fulfillment=payload.fulfillment,
        delivery_zone_id=payload.delivery_zone_id,
        delivery_address=payload.delivery_address,
        comment=payload.comment,
        user_id=user_id,
    )
    audit(
        db,
        "subscription.create",
        actor=_actor(user),
        user_id=user.id,
        tenant_id=tenant_id,
        entity="subscription",
        entity_id=str(sub.id),
        details={
            "interval_days": sub.interval_days,
            "next_order_date": sub.next_order_date.isoformat(),
            "items": len(payload.items),
        },
    )
    db.commit()
    db.refresh(sub)
    return _payload(db, sub)


@admin_router.patch("/{sub_id}", summary="Изменить регулярный заказ")
def subscriptions_update(
    sub_id: int,
    payload: SubscriptionPatchIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = subscription_service.require_enabled(db)
    sub = subscription_service.get_subscription(db, sub_id)
    changes = payload.model_dump(exclude_unset=True)
    subscription_service.update(
        db,
        sub,
        status=changes.get("status"),
        interval_days=changes.get("interval_days"),
        next_order_date=changes.get("next_order_date"),
        items=payload.items,
        fulfillment=changes.get("fulfillment"),
        delivery_zone_id=changes.get("delivery_zone_id"),
        delivery_address=changes.get("delivery_address"),
        comment=changes.get("comment"),
    )
    audit(
        db,
        "subscription.update",
        actor=_actor(user),
        user_id=user.id,
        tenant_id=tenant_id,
        entity="subscription",
        entity_id=str(sub.id),
        details={"fields": sorted(changes.keys()), "status": sub.status},
    )
    db.commit()
    db.refresh(sub)
    return _payload(db, sub)


@admin_router.post("/{sub_id}/run", summary="Оформить заказ по подписке сейчас")
def subscriptions_run(
    sub_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = subscription_service.require_enabled(db)
    sub = subscription_service.get_subscription(db, sub_id)
    order = subscription_service.run_now(db, sub)
    audit(
        db,
        "subscription.run",
        actor=_actor(user),
        user_id=user.id,
        tenant_id=tenant_id,
        entity="subscription",
        entity_id=str(sub.id),
        details={"order": order.number, "total": float(order.total_amount or 0)},
    )
    db.commit()
    db.refresh(sub)
    return {"subscription": _payload(db, sub), "order_number": order.number}


@account_router.get("", summary="Мои регулярные заказы")
def my_subscriptions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription_service.require_enabled(db)
    return {
        "items": subscription_service.list_subscriptions(db, user_id=user.id)
    }


@account_router.post("", summary="Оформить регулярный заказ")
def my_subscription_create(
    payload: SubscriptionCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = subscription_service.require_enabled(db)
    sub = subscription_service.create(
        db,
        tenant_id,
        customer_name=user.full_name or "Покупатель",
        phone=user.phone,
        interval_days=payload.interval_days,
        next_order_date=payload.next_order_date,
        items=payload.items,
        fulfillment=payload.fulfillment,
        delivery_zone_id=payload.delivery_zone_id,
        delivery_address=payload.delivery_address,
        comment=payload.comment,
        user_id=user.id,
    )
    audit(
        db,
        "subscription.request",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant_id,
        entity="subscription",
        entity_id=str(sub.id),
        details={"interval_days": sub.interval_days, "items": len(payload.items)},
    )
    db.commit()
    db.refresh(sub)
    return _payload(db, sub)


@account_router.patch("/{sub_id}", summary="Приостановить или отменить подписку")
def my_subscription_update(
    sub_id: int,
    payload: SubscriptionAccountPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = subscription_service.require_enabled(db)
    sub = subscription_service.get_subscription(db, sub_id)
    if sub.user_id != user.id:
        raise HTTPException(status_code=403, detail="Это не ваш регулярный заказ")
    subscription_service.update(db, sub, status=payload.status)
    audit(
        db,
        "subscription.status",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant_id,
        entity="subscription",
        entity_id=str(sub.id),
        details={"status": payload.status},
    )
    db.commit()
    db.refresh(sub)
    return _payload(db, sub)
