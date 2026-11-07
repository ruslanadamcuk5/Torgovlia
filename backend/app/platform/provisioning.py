"""Создание магазина: общий сценарий для панели платформы и публичной регистрации."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.defaults import build_defaults
from app.models import (
    DOMAIN_SUBDOMAIN,
    MEMBERSHIP_OWNER,
    ROLE_ADMIN,
    Tenant,
    TenantDomain,
    TenantMembership,
    TenantSettings,
    User,
    utcnow,
)
from app.platform.catalog import PLAN_BY_CODE
from app.platform.ops import ensure_job
from app.platform.preset_catalog import seed_preset_catalog
from app.platform.sync import ensure_tenant_services
from app.security import hash_password, validate_password
from app.services.audit import audit
from app.tenancy import tenant_host


@dataclass(frozen=True)
class CategoryPreset:
    code: str
    title: str
    description: str
    examples: tuple[str, ...]
    icon: str


CATEGORY_PRESETS = (
    CategoryPreset("fish", "Рыба и морепродукты", "Свежая рыба, копчёности, икра", ("охлаждённая рыба", "копчёности", "икра"), "fish"),
    CategoryPreset("meat", "Мясо и птица", "Вырезка, фарш, курица, индейка", ("стейки", "фарш", "птица"), "box"),
    CategoryPreset("flowers", "Цветы и растения", "Букеты, комнатные растения, подарки", ("букеты", "растения", "упаковка"), "heart"),
    CategoryPreset("vegetables", "Овощи и фрукты", "Сезонные продукты с грядки", ("овощи", "фрукты", "зелень"), "tag"),
    CategoryPreset("grocery", "Продукты", "Бакалея, молочное, напитки", ("бакалея", "молочное", "напитки"), "cart"),
    CategoryPreset("bakery", "Выпечка и кондитерка", "Хлеб, торты, десерты", ("хлеб", "торты", "десерты"), "sparkles"),
    CategoryPreset("clothing", "Одежда", "Женская, мужская, детская одежда", ("размеры", "цвета", "коллекции"), "tag"),
    CategoryPreset("shoes", "Обувь", "Обувь и аксессуары", ("размеры", "бренды", "сезон"), "box"),
    CategoryPreset("electronics", "Электроника", "Гаджеты, аксессуары, ремонт", ("характеристики", "гарантия", "доставка"), "smartphone"),
    CategoryPreset("building", "Стройматериалы", "Стройка, отделка, инструмент", ("расход", "фасовка", "доставка"), "box"),
    CategoryPreset("cosmetics", "Косметика", "Уход, парфюмерия, бытовая химия", ("бренды", "объёмы", "наборы"), "sparkles"),
    CategoryPreset("other", "Другое", "Универсальный магазин под ваши товары", ("любые товары", "услуги", "заказы"), "grid"),
)

PRESET_BY_CODE = {item.code: item for item in CATEGORY_PRESETS}

RESERVED_SLUGS = frozenset(
    {
        "www", "api", "app", "platform", "admin", "mail", "cdn", "status",
        "docs", "support", "billing", "static", "media", "assets", "auth",
        "help", "blog", "shop", "store", "login", "register", "checkout",
        "start", "signup", "tariffs", "templates", "pay", "payment",
    }
)


def ensure_slug_free(db: Session, slug: str, exclude_id: int | None = None) -> None:
    if slug in RESERVED_SLUGS:
        raise HTTPException(status_code=409, detail="Этот адрес зарезервирован платформой")
    stmt = select(Tenant.id).where(Tenant.slug == slug)
    if exclude_id:
        stmt = stmt.where(Tenant.id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status_code=409, detail="Такой адрес уже занят")


def ensure_host_free(db: Session, host: str, exclude_id: int | None = None) -> None:
    stmt = select(TenantDomain.id).where(TenantDomain.host == host.lower())
    if exclude_id:
        stmt = stmt.where(TenantDomain.tenant_id != exclude_id)
    if db.scalar(stmt):
        raise HTTPException(status_code=409, detail="Этот домен уже подключён")


def create_tenant(
    db: Session,
    *,
    slug: str,
    name: str,
    plan_code: str = "start",
    category_preset: str | None = None,
    owner_phone: str | None = None,
    owner_name: str = "",
    owner_password: str | None = None,
    locale: str = "ru",
    currency: str = "BYN",
    timezone: str = "Europe/Minsk",
    is_demo: bool = False,
    actor: str = "",
    platform_user_id: int | None = None,
    audit_action: str = "tenant.create",
) -> tuple[Tenant, User | None]:
    """Создаёт арендатора, поддомен, настройки, сервисы и владельца.

    Пароль по умолчанию не используется: публичная регистрация обязана передать
    пароль, панель платформы может создать магазин без владельца.
    """
    slug = slug.strip().lower()
    name = name.strip()
    if plan_code not in PLAN_BY_CODE:
        raise HTTPException(status_code=422, detail="Неизвестный тариф")
    if category_preset and category_preset not in PRESET_BY_CODE:
        raise HTTPException(status_code=422, detail="Неизвестная категория")

    ensure_slug_free(db, slug)
    host = tenant_host(slug)
    ensure_host_free(db, host)

    if owner_phone and owner_password:
        try:
            validate_password(owner_password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    tenant = Tenant(
        slug=slug,
        name=name,
        status="onboarding",
        plan_code=plan_code,
        category_preset=category_preset,
        locale=locale,
        currency=currency,
        timezone=timezone,
        is_demo=is_demo,
    )
    db.add(tenant)
    db.flush()

    settings_data = build_defaults()
    settings_data["brand_name"] = name
    settings_data["seo_title"] = name
    from app.platform.templates import default_template_for

    settings_data["template"] = default_template_for(category_preset)
    db.add(TenantSettings(tenant_id=tenant.id, data=settings_data))
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
    ensure_tenant_services(db, tenant)
    seed_preset_catalog(db, tenant.id, category_preset)
    if not is_demo:
        # Новый магазин сразу попадает в очередь запуска платформы.
        ensure_job(db, tenant)

    owner: User | None = None
    if owner_phone:
        if not owner_password:
            raise HTTPException(status_code=422, detail="Укажите пароль владельца")
        owner = User(
            tenant_id=tenant.id,
            phone=owner_phone,
            full_name=owner_name or name,
            role=ROLE_ADMIN,
            password_hash=hash_password(owner_password),
            is_phone_verified=True,
            consent_personal_data=True,
        )
        db.add(owner)
        db.flush()
        db.add(
            TenantMembership(tenant_id=tenant.id, user_id=owner.id, role=MEMBERSHIP_OWNER)
        )

    audit(
        db,
        audit_action,
        actor=actor or owner_phone or "signup",
        user_id=owner.id if owner else None,
        platform_user_id=platform_user_id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={
            "slug": slug,
            "host": host,
            "plan": plan_code,
            "category": category_preset,
            "owner_phone": owner_phone,
        },
    )
    db.commit()
    db.refresh(tenant)
    return tenant, owner
