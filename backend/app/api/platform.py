"""API панели платформы: арендаторы, домены, статистика.

На этом этапе доступ проверяется существующей ролью admin. После появления
platform_users сюда будет подключена отдельная авторизация платформы.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_admin
from app.models import (
    TENANT_ACTIVE,
    TENANT_ARCHIVED,
    TENANT_SUSPENDED,
    DOMAIN_SUBDOMAIN,
    Tenant,
    TenantDomain,
    TenantSettings,
    User,
    utcnow,
)
from app.schemas import (
    PlatformStatsOut,
    TenantCreateIn,
    TenantDomainIn,
    TenantDomainOut,
    TenantOut,
    TenantPatchIn,
)
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
def platform_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
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


@router.get("/tenants", summary="Список арендаторов")
def list_tenants(
    _: User = Depends(require_admin),
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
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    slug = payload.slug.strip().lower()
    _ensure_slug_free(db, slug)
    host = tenant_host(slug)
    _ensure_host_free(db, host)

    tenant = Tenant(
        slug=slug,
        name=payload.name.strip(),
        status="onboarding",
        plan_code=payload.plan_code,
        category_preset=payload.category_preset,
        locale=payload.locale,
        currency=payload.currency,
        timezone=payload.timezone,
        is_demo=payload.is_demo,
    )
    db.add(tenant)
    db.flush()

    db.add(TenantSettings(tenant_id=tenant.id, data={}))
    db.add(
        TenantDomain(
            tenant_id=tenant.id,
            host=host,
            kind=DOMAIN_SUBDOMAIN,
            is_primary=True,
            verified_at=utcnow(),
            ssl_status="pending",
            dns_status="ok",
        )
    )
    audit(
        db,
        "tenant.create",
        actor=user.full_name or user.phone,
        user_id=user.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"slug": slug, "host": host, "plan": payload.plan_code},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/tenants/{tenant_id}", response_model=TenantOut, summary="Карточка арендатора")
def get_tenant(
    tenant_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _tenant_or_404(db, tenant_id)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut, summary="Изменить арендатора")
def update_tenant(
    tenant_id: int,
    payload: TenantPatchIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] == TENANT_ARCHIVED:
        # Архивация — обратимое действие, но сайт сразу перестаёт резолвиться.
        changes.setdefault("status", TENANT_ARCHIVED)
    for field, value in changes.items():
        setattr(tenant, field, value)
    audit(
        db,
        "tenant.update",
        actor=user.full_name or user.phone,
        user_id=user.id,
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
    _: User = Depends(require_admin),
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
    user: User = Depends(require_admin),
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
        user_id=user.id,
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
    user: User = Depends(require_admin),
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
        user_id=user.id,
        entity="tenant",
        entity_id=str(tenant_id),
        details={"host": domain.host},
    )
    db.delete(domain)
    db.commit()
    return None
