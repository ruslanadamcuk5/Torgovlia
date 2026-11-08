"""Сервис настроек сайта: чтение, сохранение, публичная проекция.

Настройки хранятся в tenant_settings. Для запросов без арендатора (панель
платформы, старые миграции) используется SiteSetting(id=1) как fallback.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.defaults import build_defaults
from app.models import SiteSetting, TenantSettings
from app.schemas import SiteSettings
from app.tenancy import current_tenant


PUBLIC_FIELDS = {
    "brand_name", "template", "accent_color", "tagline", "city", "market_name", "pavilion", "address", "phone", "phone_secondary",
    "email", "working_hours", "socials", "logo_url", "favicon_url", "hero_image_url", "hero_badge",
    "hero_title", "hero_subtitle", "hero_note", "about_title", "about_text", "announcement",
    "announcement_active", "banners", "advantages", "pickup_rules", "payment_note", "privacy_policy",
    "offer_text", "contacts_extra", "min_order_amount", "lead_time_minutes", "slot_step_minutes",
    "booking_days_ahead", "slot_capacity", "max_items", "android_apk_url", "android_app_version",
    "android_app_size", "app_install_url", "seo_title", "seo_description", "seo_keywords",
    "seo_og_image_url", "seo_indexing", "analytics_yandex", "analytics_google",
    "analytics_meta_pixel", "map_url",
    "map_embed_url", "legal_name", "unp", "legal_address",
}


def _deep_merge(base: dict, extra: dict) -> dict:
    result = dict(base)
    for key, value in (extra or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result:
            result[key] = value
    return result


def _legacy_row(db: Session) -> SiteSetting:
    row = db.get(SiteSetting, 1)
    if not row:
        row = SiteSetting(id=1, data=build_defaults())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _tenant_row(db: Session, tenant_id: int) -> TenantSettings:
    row = db.get(TenantSettings, tenant_id)
    if row:
        return row
    tenant = current_tenant()
    data = build_defaults()
    if tenant:
        data["brand_name"] = tenant.name
        data["seo_title"] = tenant.name
    row = TenantSettings(tenant_id=tenant_id, data=data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _row(db: Session):
    tenant = current_tenant()
    if tenant:
        return _tenant_row(db, tenant.id)
    return _legacy_row(db)


def get_settings_model(db: Session) -> SiteSettings:
    row = _row(db)
    merged = _deep_merge(build_defaults(), row.data or {})
    # Рабочие часы и баннеры — списки, их нельзя мержить построчно
    if not merged.get("working_hours"):
        merged["working_hours"] = build_defaults()["working_hours"]
    return SiteSettings.model_validate(merged)


def settings_for_tenant(db: Session, tenant_id: int) -> SiteSettings:
    """Настройки конкретного магазина без зависимости от текущего контекста."""
    row = db.get(TenantSettings, tenant_id)
    merged = _deep_merge(build_defaults(), (row.data if row else None) or {})
    if not merged.get("working_hours"):
        merged["working_hours"] = build_defaults()["working_hours"]
    return SiteSettings.model_validate(merged)


def get_public_settings(db: Session) -> dict:
    model = get_settings_model(db)
    data = {k: v for k, v in model.model_dump().items() if k in PUBLIC_FIELDS}
    min_order = f"{model.min_order_amount:.2f} BYN".replace(".", ",")
    data["pickup_rules"] = (model.pickup_rules or "").replace("{min_order}", min_order)
    return data


def save_settings(db: Session, payload: SiteSettings) -> SiteSettings:
    row = _row(db)
    row.data = payload.model_dump()
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return get_settings_model(db)


def settings_updated_at(db: Session) -> datetime | None:
    row = _row(db)
    return row.updated_at if row else None


def pickup_rules_text(db: Session) -> str:
    model = get_settings_model(db)
    text = model.pickup_rules or ""
    return text.replace("{min_order}", f"{model.min_order_amount:.2f} BYN".replace(".", ","))
