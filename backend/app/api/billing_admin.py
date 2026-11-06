"""Оплата и подписка в админке магазина."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Plan, Tenant, User
from app.platform.billing import billing_overview, list_invoices, request_plan
from app.schemas import BillingPageOut, InvoiceOut, PlanChangeIn
from app.services.audit import audit
from app.tenancy import current_tenant


router = APIRouter(prefix="/admin/billing", tags=["Оплата магазина"])


def _tenant(db: Session) -> Tenant:
    context = current_tenant()
    tenant = db.get(Tenant, context.id) if context else None
    if not tenant:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return tenant


@router.get("", response_model=BillingPageOut, summary="Тариф, подписка и счета")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = _tenant(db)
    data = billing_overview(db, tenant)
    plans = db.scalars(select(Plan).order_by(Plan.sort_order)).all()
    data["plans"] = [
        {
            "code": plan.code,
            "title": plan.title,
            "description": plan.description,
            "price_month": float(plan.price_month),
            "price_year": float(plan.price_year),
            "quotas": plan.quotas or {},
        }
        for plan in plans
    ]
    return data


@router.get("/invoices", response_model=list[InvoiceOut], summary="Счета магазина")
def invoices(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    tenant = _tenant(db)
    return list_invoices(db, tenant.id)


@router.post("/plan", summary="Сменить тариф")
def change_plan(
    payload: PlanChangeIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant(db)
    result = request_plan(db, tenant, payload.plan_code)
    audit(
        db,
        "billing.plan_request",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant.id,
        entity="subscription",
        details={"plan_code": payload.plan_code, "applied": result.get("applied")},
    )
    db.commit()
    return result
