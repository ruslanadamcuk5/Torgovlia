"""API панели платформы: арендаторы, домены, статистика.

На этом этапе доступ проверяется существующей ролью admin. После появления
platform_users сюда будет подключена отдельная авторизация платформы.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_platform
from app.models import (
    ROLE_ADMIN,
    TENANT_ACTIVE,
    TENANT_ARCHIVED,
    TENANT_SUSPENDED,
    DOMAIN_SUBDOMAIN,
    Invoice,
    PlatformUser,
    Tenant,
    TenantDomain,
    TenantService,
    User,
    utcnow,
)
from app.platform.billing import (
    _apply_plan,
    cancel_invoice,
    create_invoice,
    invoice_payload,
    list_invoices,
    mark_paid,
)
from app.platform import dashboard as dashboard_module
from app.platform.catalog import (
    PLANS,
    SERVICE_BY_CODE,
    SERVICE_CATALOG,
    SERVICE_SETUP,
    STATUS_TITLES,
    included_in_plan,
    service_status,
)
from app.platform.entitlements import list_for_tenant, platform_update
from app.platform.service_details import detail_for
from app.platform.lifecycle import apply_action, lifecycle_payload
from app.platform.provisioning import create_tenant as create_tenant_record
from app.platform.sync import ensure_tenant_services
from app.schemas import (
    DashboardOut,
    ImpersonationIn,
    ImpersonationOut,
    InvoiceOut,
    LifecycleIn,
    LifecycleOut,
    PlatformInvoiceCreateIn,
    PlatformInvoiceOut,
    PlatformServiceOut,
    PlatformServiceUpdateIn,
    PlanChangeIn,
    PlatformStatsOut,
    ServiceListOut,
    TenantCreateIn,
    TenantDomainIn,
    TenantDomainOut,
    TenantOut,
    TenantPatchIn,
)
from app.security import create_impersonation_token
from app.services.audit import audit
from app.tenancy import tenant_host


router = APIRouter(prefix="/platform", tags=["Платформа"])


def _tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.domains))
    )
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Арендатор не найден")
    return tenant


def _ensure_slug_free(db: Session, slug: str, exclude_id: int | None = None) -> None:
    stmt = select(Tenant.id).where(Tenant.slug == slug)
    if exclude_id:
        stmt = stmt.where(Tenant.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой адрес уже занят")


def _ensure_host_free(db: Session, host: str, exclude_id: int | None = None) -> None:
    stmt = select(TenantDomain.id).where(TenantDomain.host == host)
    if exclude_id:
        stmt = stmt.where(TenantDomain.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот домен уже подключён")


@router.get("/stats", response_model=PlatformStatsOut, summary="Сводка платформы")
def platform_stats(_: PlatformUser = Depends(require_platform), db: Session = Depends(get_db)):
    by_status = dict(
        db.execute(select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)).all()
    )
    return {
        "tenants_total": int(sum(by_status.values())),
        "tenants_active": int(by_status.get(TENANT_ACTIVE, 0)),
        "tenants_trial": int(by_status.get("onboarding", 0)),
        "tenants_suspended": int(by_status.get(TENANT_SUSPENDED, 0)),
        "domains_total": int(db.scalar(select(func.count(TenantDomain.id))) or 0),
        "by_status": {key: int(value) for key, value in by_status.items()},
    }


@router.get("/dashboard", response_model=DashboardOut, summary="Показатели платформы")
def platform_dashboard(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return dashboard_module.overview(db)


@router.get(
    "/tenants/{tenant_id}/lifecycle",
    response_model=LifecycleOut,
    summary="Доступные действия жизненного цикла",
)
def tenant_lifecycle(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    return lifecycle_payload(tenant)


@router.post(
    "/tenants/{tenant_id}/lifecycle",
    response_model=LifecycleOut,
    summary="Изменить жизненный цикл магазина",
)
def change_lifecycle(
    tenant_id: int,
    payload: LifecycleIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    tenant = apply_action(
        db,
        tenant,
        payload.action,
        reason=payload.reason,
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
    )
    db.refresh(tenant)
    return lifecycle_payload(tenant)


@router.post(
    "/tenants/{tenant_id}/impersonate",
    response_model=ImpersonationOut,
    summary="Войти в магазин от имени сотрудника платформы",
)
def impersonate_tenant(
    tenant_id: int,
    payload: ImpersonationIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    stmt = select(User).where(
        User.tenant_id == tenant.id,
        User.is_active.is_(True),
        User.role == ROLE_ADMIN,
    )
    if payload.user_id:
        stmt = stmt.where(User.id == payload.user_id)
    target = db.scalars(
        stmt.order_by(User.created_at).execution_options(skip_tenant_filter=True)
    ).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="У магазина нет активного администратора",
        )

    token = create_impersonation_token(
        target.id,
        target.role,
        platform_user_id=user.id,
        reason=payload.reason,
    )
    audit(
        db,
        "tenant.impersonate",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="user",
        entity_id=str(target.id),
        details={"reason": payload.reason.strip(), "target_phone": target.phone},
    )
    db.commit()
    return {
        "access_token": token,
        "expires_in": 30 * 60,
        "tenant_id": tenant.id,
        "tenant_slug": tenant.slug,
        "host": tenant_host(tenant.slug),
        "user": target,
    }


@router.get("/tenants", summary="Список арендаторов")
def list_tenants(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Tenant).options(selectinload(Tenant.domains))
    count_stmt = select(func.count(Tenant.id))
    if status_filter:
        stmt = stmt.where(Tenant.status == status_filter)
        count_stmt = count_stmt.where(Tenant.status == status_filter)
    if q:
        pattern = f"%{q.strip().lower()}%"
        condition = or_(
            func.lower(Tenant.name).like(pattern),
            func.lower(Tenant.slug).like(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = int(db.scalar(count_stmt) or 0)
    items = db.scalars(stmt.order_by(Tenant.created_at.desc()).limit(limit).offset(offset)).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [TenantOut.model_validate(item) for item in items],
    }


@router.post(
    "/tenants",
    response_model=TenantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать арендатора",
)
def create_tenant(
    payload: TenantCreateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant, _ = create_tenant_record(
        db,
        slug=payload.slug,
        name=payload.name,
        plan_code=payload.plan_code,
        category_preset=payload.category_preset,
        owner_phone=payload.owner_phone,
        owner_name=payload.owner_name,
        owner_password=payload.owner_password,
        locale=payload.locale,
        currency=payload.currency,
        timezone=payload.timezone,
        is_demo=payload.is_demo,
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
    )
    return tenant


@router.get("/tenants/{tenant_id}", response_model=TenantOut, summary="Карточка арендатора")
def get_tenant(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return _tenant_or_404(db, tenant_id)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut, summary="Изменить арендатора")
def update_tenant(
    tenant_id: int,
    payload: TenantPatchIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] == TENANT_ARCHIVED:
        # Архивация — обратимое действие, но сайт сразу перестаёт резолвиться.
        changes.setdefault("status", TENANT_ARCHIVED)
    plan_code = changes.pop("plan_code", None)
    for field, value in changes.items():
        setattr(tenant, field, value)
    if plan_code and plan_code != tenant.plan_code:
        _apply_plan(db, tenant, plan_code)
    audit(
        db,
        "tenant.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get(
    "/tenants/{tenant_id}/domains",
    response_model=list[TenantDomainOut],
    summary="Домены арендатора",
)
def list_domains(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    _tenant_or_404(db, tenant_id)
    return db.scalars(
        select(TenantDomain)
        .where(TenantDomain.tenant_id == tenant_id)
        .order_by(TenantDomain.is_primary.desc(), TenantDomain.created_at)
    ).all()


@router.post(
    "/tenants/{tenant_id}/domains",
    response_model=TenantDomainOut,
    status_code=status.HTTP_201_CREATED,
    summary="Подключить домен",
)
def add_domain(
    tenant_id: int,
    payload: TenantDomainIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    host = payload.host.strip().lower().rstrip(".")
    _ensure_host_free(db, host)
    if payload.is_primary:
        for domain in tenant.domains:
            domain.is_primary = False
    domain = TenantDomain(
        tenant_id=tenant.id,
        host=host,
        kind=payload.kind,
        is_primary=payload.is_primary,
        ssl_status="none",
        dns_status="pending",
    )
    db.add(domain)
    audit(
        db,
        "tenant.domain.add",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"host": host, "kind": payload.kind},
    )
    db.commit()
    db.refresh(domain)
    return domain


@router.delete(
    "/tenants/{tenant_id}/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отключить домен",
)
def remove_domain(
    tenant_id: int,
    domain_id: int,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    domain = db.scalar(
        select(TenantDomain).where(
            TenantDomain.id == domain_id, TenantDomain.tenant_id == tenant_id
        )
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Домен не найден")
    if domain.is_primary:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить основной домен. Сначала назначьте другой.",
        )
    audit(
        db,
        "tenant.domain.remove",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant_id),
        details={"host": domain.host},
    )
    db.delete(domain)
    db.commit()
    return None


# ─── Сервисы: каталог и управление ───────────────────────────────

@router.get("/catalog", summary="Каталог сервисов и тарифов платформы")
def service_catalog(_: PlatformUser = Depends(require_platform)):
    return {
        "plans": [
            {
                "code": plan.code,
                "title": plan.title,
                "description": plan.description,
                "price_month": float(plan.price_month),
                "price_year": float(plan.price_year),
                "quotas": plan.quotas,
            }
            for plan in PLANS
        ],
        "services": [
            {
                "code": item.code,
                "title": item.title,
                "group": item.group,
                "description": item.description,
                "tier": item.tier,
                "price_month": float(item.price_month),
                "dependencies": list(item.dependencies),
                "included": {plan.code: included_in_plan(item.code, plan.code) for plan in PLANS},
                "status": service_status(item.code)[0],
                "status_title": STATUS_TITLES[service_status(item.code)[0]],
                "status_note": service_status(item.code)[1],
                "setup_route": SERVICE_SETUP.get(item.code, ""),
                "icon": item.icon,
            }
            for item in SERVICE_CATALOG
        ],
    }


@router.get("/catalog/{code}", summary="Подробно о сервисе платформы")
def service_catalog_detail(
    code: str,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    item = SERVICE_BY_CODE.get(code)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сервис не найден")

    detail = detail_for(code)
    rows = db.execute(
        select(TenantService, Tenant)
        .join(Tenant, Tenant.id == TenantService.tenant_id)
        .where(TenantService.service_code == code)
        .order_by(Tenant.name)
        .execution_options(skip_tenant_filter=True)
    ).all()

    tenants = []
    for row, tenant in rows:
        active = row.status in ("enabled", "trial")
        tenants.append(
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "plan_code": tenant.plan_code,
                "status": row.status,
                "enabled": active,
                "is_demo": tenant.is_demo,
            }
        )

    enabled_count = sum(1 for tenant in tenants if tenant["enabled"])
    price = float(item.price_month or 0)

    def catalog_link(other) -> dict:
        return {
            "code": other.code,
            "title": other.title,
            "group": other.group,
            "description": other.description,
            "tier": other.tier,
            "price_month": float(other.price_month or 0),
            "status": service_status(other.code)[0],
            "status_title": STATUS_TITLES[service_status(other.code)[0]],
            "status_note": service_status(other.code)[1],
        }

    related = [
        catalog_link(other)
        for other in SERVICE_CATALOG
        if other.group == item.group and other.code != code
    ][:6]
    dependency_services = [
        catalog_link(SERVICE_BY_CODE[dep]) for dep in item.dependencies if dep in SERVICE_BY_CODE
    ]

    return {
        "code": item.code,
        "title": item.title,
        "group": item.group,
        "description": item.description,
        "tier": item.tier,
        "price_month": price,
        "dependencies": list(item.dependencies),
        "included": {plan.code: included_in_plan(item.code, plan.code) for plan in PLANS},
        "status": service_status(item.code)[0],
        "status_title": STATUS_TITLES[service_status(item.code)[0]],
        "status_note": service_status(item.code)[1],
        "setup_route": SERVICE_SETUP.get(item.code, ""),
        "icon": item.icon,
        "about": detail.get("about") or item.description,
        "audience": detail.get("audience") or "",
        "features": list(detail.get("features") or []),
        "related": related,
        "dependency_services": dependency_services,
        "usage": {
            "enabled": enabled_count,
            "total": len(tenants),
            "revenue_month": round(price * enabled_count, 2) if item.tier == "addon" else 0.0,
            "tenants": tenants,
        },
    }


@router.get(
    "/tenants/{tenant_id}/services",
    response_model=ServiceListOut,
    summary="Сервисы арендатора",
)
def tenant_services(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    items, plan_code = list_for_tenant(db, tenant)
    return {"plan_code": plan_code, "items": items}


@router.patch(
    "/tenants/{tenant_id}/services/{code}",
    response_model=PlatformServiceOut,
    summary="Принудительно изменить сервис арендатора",
)
def update_tenant_service(
    tenant_id: int,
    code: str,
    payload: PlatformServiceUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    result = platform_update(
        db,
        tenant,
        code,
        status_value=payload.status,
        locked_by_platform=payload.locked_by_platform,
        config=payload.config,
    )
    audit(
        db,
        "service.platform_update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="service",
        entity_id=code,
        details={"status": payload.status, "locked": payload.locked_by_platform},
    )
    db.commit()
    return {**result, "tenant_id": tenant.id}


# ─── Счета и оплата ──────────────────────────────────────────────

def _invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .execution_options(skip_tenant_filter=True)
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    return invoice


@router.get("/invoices", response_model=list[PlatformInvoiceOut], summary="Все счета платформы")
def all_invoices(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    tenant_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if tenant_id:
        stmt = stmt.where(Invoice.tenant_id == tenant_id)
    rows = db.scalars(stmt.execution_options(skip_tenant_filter=True)).all()
    return [{**invoice_payload(item), "tenant_id": item.tenant_id} for item in rows]


@router.get(
    "/tenants/{tenant_id}/invoices",
    response_model=list[InvoiceOut],
    summary="Счета арендатора",
)
def tenant_invoices(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    _tenant_or_404(db, tenant_id)
    return list_invoices(db, tenant_id)


@router.post(
    "/tenants/{tenant_id}/invoices",
    response_model=PlatformInvoiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Выставить счёт",
)
def create_tenant_invoice(
    tenant_id: int,
    payload: PlatformInvoiceCreateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    invoice = create_invoice(
        db,
        tenant,
        kind=payload.kind,
        amount=payload.amount,
        description=payload.description,
        plan_code=payload.plan_code,
        service_code=payload.service_code,
        period_days=payload.period_days,
        due_days=payload.due_days,
    )
    audit(
        db,
        "billing.invoice.create",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="invoice",
        entity_id=str(invoice.id),
        details={"amount": float(invoice.amount), "kind": invoice.kind},
    )
    db.commit()
    return {**invoice_payload(invoice), "tenant_id": tenant.id}


@router.post(
    "/invoices/{invoice_id}/paid",
    response_model=PlatformInvoiceOut,
    summary="Отметить счёт оплаченным",
)
def pay_invoice(
    invoice_id: int,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    method: str = "manual",
    external_id: str | None = None,
):
    invoice = _invoice_or_404(db, invoice_id)
    invoice = mark_paid(db, invoice, method=method, external_id=external_id)
    audit(
        db,
        "billing.invoice.paid",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=invoice.tenant_id,
        entity="invoice",
        entity_id=str(invoice.id),
        details={"amount": float(invoice.amount)},
    )
    db.commit()
    return {**invoice_payload(invoice), "tenant_id": invoice.tenant_id}


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=PlatformInvoiceOut,
    summary="Отменить счёт",
)
def cancel_platform_invoice(
    invoice_id: int,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    reason: str = "",
):
    invoice = _invoice_or_404(db, invoice_id)
    invoice = cancel_invoice(db, invoice, reason)
    audit(
        db,
        "billing.invoice.cancel",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=invoice.tenant_id,
        entity="invoice",
        entity_id=str(invoice.id),
    )
    db.commit()
    return {**invoice_payload(invoice), "tenant_id": invoice.tenant_id}


@router.post(
    "/tenants/{tenant_id}/plan",
    summary="Принудительно сменить тариф арендатора",
)
def force_plan(
    tenant_id: int,
    payload: PlanChangeIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    _apply_plan(db, tenant, payload.plan_code)
    audit(
        db,
        "billing.plan_force",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="subscription",
        details={"plan_code": payload.plan_code},
    )
    db.commit()
    return {"ok": True, "plan_code": payload.plan_code}
