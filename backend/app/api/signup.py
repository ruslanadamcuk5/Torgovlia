"""Публичная регистрация магазина: каталог тарифов и создание сайта."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import client_ip
from app.models import Plan
from app.platform.billing import KIND_SUBSCRIPTION, create_invoice, invoice_payload
from app.platform.catalog import PLAN_BY_CODE, PLANS
from app.platform import settings as platform_settings
from app.platform.provisioning import CATEGORY_PRESETS, RESERVED_SLUGS, create_tenant
from app.schemas import (
    CategoryPresetOut,
    PlanOut,
    SignupCatalogOut,
    SignupIn,
    SignupOut,
)
from app.tenancy import tenant_host


router = APIRouter(prefix="/signup", tags=["Регистрация магазина"])

_WINDOW_SECONDS = 60 * 60
_MAX_ATTEMPTS = 6
_attempts: dict[str, list[float]] = {}


def _check_limit(ip: str) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _attempts.get(ip, []) if now - stamp < _WINDOW_SECONDS]
    _attempts[ip] = recent
    if len(recent) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток регистрации. Попробуйте через час.",
        )


def _remember(ip: str) -> None:
    _attempts.setdefault(ip, []).append(time.monotonic())


@router.get("/catalog", response_model=SignupCatalogOut, summary="Тарифы и категории для регистрации")
def catalog(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).order_by(Plan.sort_order)).all()
    plans = {item.code: item for item in rows}
    plans_payload = []
    for definition in PLANS:
        plan = plans.get(definition.code)
        if not plan:
            continue
        plans_payload.append(
            PlanOut(
                code=plan.code,
                title=plan.title,
                description=plan.description,
                price_month=float(plan.price_month),
                price_year=float(plan.price_year),
                quotas=plan.quotas or {},
            )
        )
    return SignupCatalogOut(
        plans=plans_payload,
        categories=[
            CategoryPresetOut(
                code=item.code,
                title=item.title,
                description=item.description,
                examples=list(item.examples),
                icon=item.icon,
            )
            for item in CATEGORY_PRESETS
        ],
    )


@router.get("/check-slug", summary="Проверить адрес магазина")
def check_slug(slug: str, db: Session = Depends(get_db)):
    value = slug.strip().lower()
    import re

    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
        return {"slug": value, "available": False, "reason": "Только латиница, цифры и дефис, от 2 до 63 символов"}
    if value in RESERVED_SLUGS:
        return {"slug": value, "available": False, "reason": "Этот адрес зарезервирован"}
    from app.models import Tenant

    if db.scalar(select(Tenant.id).where(Tenant.slug == value)):
        return {"slug": value, "available": False, "reason": "Адрес уже занят"}
    return {"slug": value, "available": True, "reason": ""}


@router.post("", response_model=SignupOut, status_code=status.HTTP_201_CREATED, summary="Создать магазин")
def signup(payload: SignupIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request) or "unknown"
    _check_limit(ip)
    if not payload.offer_accepted:
        raise HTTPException(status_code=422, detail="Подтвердите согласие с условиями")

    config = platform_settings.get_config(db)
    if not config.get("allow_signups", True):
        raise HTTPException(
            status_code=403,
            detail="Самостоятельная регистрация временно приостановлена. Напишите в поддержку.",
        )
    max_tenants = int(config.get("max_tenants") or 0)
    if max_tenants:
        from app.models import Tenant

        current = db.scalar(select(func.count(Tenant.id))) or 0
        if current >= max_tenants:
            raise HTTPException(
                status_code=409,
                detail="Достигнут лимит магазинов на платформе. Напишите в поддержку.",
            )

    plan_code = payload.plan_code or str(config.get("default_plan_code") or "start")
    _remember(ip)
    tenant, _ = create_tenant(
        db,
        slug=payload.slug,
        name=payload.name,
        plan_code=plan_code,
        category_preset=payload.category_preset,
        owner_phone=payload.owner_phone,
        owner_name=payload.owner_name,
        owner_password=payload.owner_password,
        actor=payload.owner_phone,
        audit_action="tenant.signup",
    )

    plan = PLAN_BY_CODE.get(plan_code)
    invoice = None
    if plan and plan.price_month > 0:
        invoice = create_invoice(
            db,
            tenant,
            kind=KIND_SUBSCRIPTION,
            amount=plan.price_month,
            description=f"Первый месяц тарифа «{plan.title}»",
            plan_code=plan_code,
            period_days=30,
            due_days=7,
        )

    return SignupOut(
        tenant_id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        host=tenant_host(tenant.slug),
        status=tenant.status,
        plan_code=tenant.plan_code,
        plan_title=plan.title if plan else tenant.plan_code,
        price_month=float(plan.price_month) if plan else 0,
        owner_phone=payload.owner_phone,
        invoice=invoice_payload(invoice) if invoice else None,
    )
