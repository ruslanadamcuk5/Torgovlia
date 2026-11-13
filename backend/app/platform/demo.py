"""Автосброс демо-магазина к исходному состоянию.

Демо открыто всем, поэтому за сутки в нём появляются тестовые заказы, чаты и
корзины. Раз в `DEMO_RESET_HOURS` магазин возвращается к аккуратному состоянию:
транзакционные данные удаляются, демо-контент создаётся заново. Отметка о
последнем сбросе хранится в настройках арендатора, поэтому отдельная таблица
и миграция не нужны.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Appointment,
    Campaign,
    CampaignRecipient,
    Cart,
    Category,
    ChatMessage,
    ChatThread,
    CustomerNote,
    CustomerTag,
    GiftCertificate,
    GiftCertificateTransaction,
    RegularOrder,
    RegularOrderItem,
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    OrderItem,
    PriceImport,
    Product,
    PromoCode,
    PurchaseItem,
    PurchaseOrder,
    Review,
    Specialist,
    StaffTask,
    StockMovement,
    Supplier,
    Tenant,
    TenantSettings,
    UpsellRule,
)


log = logging.getLogger("torgovlia.demo")

MARKER = "demo_reset_at"

# Порядок важен: сначала строки-потомки, потом родители.
CHILD_TABLES = (
    Appointment,
    CampaignRecipient,
    Campaign,
    ChatMessage,
    ChatThread,
    StaffTask,
    GiftCertificateTransaction,
    GiftCertificate,
    RegularOrderItem,
    RegularOrder,
    OrderItem,
    Order,
    Cart,
    Review,
    LoyaltyTransaction,
    LoyaltyAccount,
    CustomerNote,
    CustomerTag,
    PurchaseItem,
    PurchaseOrder,
    Supplier,
    StockMovement,
    PriceImport,
    UpsellRule,
    PromoCode,
    Product,
    Specialist,
    Category,
)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def last_reset(db: Session, tenant: Tenant) -> datetime | None:
    row = db.get(TenantSettings, tenant.id)
    if row is None:
        return None
    return _parse((row.data or {}).get(MARKER))


def _mark(db: Session, tenant: Tenant, moment: datetime | None = None) -> None:
    row = db.get(TenantSettings, tenant.id)
    if row is None:
        row = TenantSettings(tenant_id=tenant.id, data={})
        db.add(row)
    data = dict(row.data or {})
    data[MARKER] = (moment or datetime.now(timezone.utc)).isoformat()
    row.data = data
    db.flush()


def is_due(db: Session, tenant: Tenant, hours: int | None = None) -> bool:
    window = settings.demo_reset_hours if hours is None else hours
    if window <= 0 or not tenant.is_demo:
        return False
    moment = last_reset(db, tenant)
    if moment is None:
        # Первый запуск: контент только что создан, сбрасывать нечего.
        _mark(db, tenant)
        db.commit()
        return False
    return moment <= datetime.now(timezone.utc) - timedelta(hours=window)


def reset(db: Session, tenant: Tenant) -> dict:
    """Удаляет данные демо-магазина и наполняет его заново."""
    for model in CHILD_TABLES:
        db.execute(delete(model).where(model.tenant_id == tenant.id))
    db.commit()

    from app.demo_odezhda import enrich
    from app.seed import _polish_demo_settings, _seed_delivery_zones

    spec = {
        "slug": tenant.slug,
        "brand": tenant.name,
        "preset": tenant.category_preset,
        "business_type": tenant.business_type,
    }
    _polish_demo_settings(db, tenant, spec)
    if tenant.business_type in ("services", "hybrid"):
        from app.platform.provisioning import apply_service_defaults
        from app.platform.service_presets import seed_service_catalog

        row = db.get(TenantSettings, tenant.id)
        if row is not None:
            data = dict(row.data or {})
            data = apply_service_defaults(data, tenant.name)
            row.data = data
        seed_service_catalog(db, tenant.id, tenant.category_preset)
    if settings.demo_content and tenant.slug == "odezhda":
        enrich(db, tenant)
    _seed_delivery_zones(db, tenant)
    _mark(db, tenant)
    db.commit()
    log.info("Демо-магазин сброшен: %s", tenant.slug)
    return {"slug": tenant.slug, "reset_at": last_reset(db, tenant)}


def demo_tenant(db: Session) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == settings.demo_tenant_slug))


def service_demo_tenant(db: Session) -> Tenant | None:
    slug = settings.service_demo_tenant_slug
    if not slug:
        return None
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def demo_tenants(db: Session) -> list[Tenant]:
    """Все публичные демо: товарный флагман и сервисный салон."""
    items = [demo_tenant(db), service_demo_tenant(db)]
    unique: list[Tenant] = []
    for tenant in items:
        if tenant is not None and all(item.id != tenant.id for item in unique):
            unique.append(tenant)
    return unique


def maybe_reset(db: Session) -> bool:
    """Ленивый сброс при первом запросе после истечения окна."""
    reset_any = False
    for tenant in demo_tenants(db):
        if not is_due(db, tenant):
            continue
        try:
            reset(db, tenant)
            reset_any = True
        except Exception as exc:  # noqa: BLE001 — демо не должно ронять сайт
            db.rollback()
            log.warning("Не удалось сбросить демо %s: %s", tenant.slug, exc)
    return reset_any
