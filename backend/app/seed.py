"""Инициализация базы: настройки, администратор, демонстрационный каталог."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.db import SessionLocal
from app.defaults import build_defaults
from app.models import (
    DOMAIN_SUBDOMAIN,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_SELLER,
    TENANT_ACTIVE,
    Category,
    Product,
    SiteSetting,
    Tenant,
    TenantDomain,
    TenantSettings,
    User,
    utcnow,
)
from app.seed_data import CATEGORIES, PRODUCTS
from app.security import hash_password
from app.utils import money, slugify


log = logging.getLogger("rybnaya.seed")


def _seed_settings(db: Session) -> None:
    if db.get(SiteSetting, 1):
        return
    db.add(SiteSetting(id=1, data=build_defaults()))
    db.commit()
    log.info("Настройки сайта созданы")


def _seed_tenant(db: Session) -> Tenant | None:
    """Создаёт арендатора по умолчанию и его основной поддомен."""
    slug = app_settings.default_tenant_slug
    if not slug:
        return None
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant:
        return tenant
    tenant = Tenant(
        slug=slug,
        name=app_settings.app_name,
        status=TENANT_ACTIVE,
        plan_code="start",
        category_preset="fish",
    )
    db.add(tenant)
    db.flush()
    db.add(TenantSettings(tenant_id=tenant.id, data=build_defaults()))
    db.add(
        TenantDomain(
            tenant_id=tenant.id,
            host=f"{slug}.{app_settings.platform_base_domain}".lower(),
            kind=DOMAIN_SUBDOMAIN,
            is_primary=True,
            verified_at=utcnow(),
            ssl_status="pending",
            dns_status="ok",
        )
    )
    db.commit()
    log.info("Создан арендатор по умолчанию: %s", slug)
    return tenant


def _seed_user(db: Session, phone: str, password: str, name: str, role: str) -> User | None:
    if db.scalar(select(User).where(User.phone == phone)):
        return None
    user = User(
        phone=phone,
        full_name=name,
        role=role,
        password_hash=hash_password(password),
        is_phone_verified=True,
        consent_personal_data=True,
    )
    db.add(user)
    db.commit()
    return user


def _seed_catalog(db: Session, tenant_id: int) -> None:
    category_map: dict[str, Category] = {}
    for item in CATEGORIES:
        category = db.scalar(
            select(Category).where(Category.slug == item["slug"], Category.tenant_id == tenant_id)
        )
        if not category:
            category = Category(**item, tenant_id=tenant_id)
            db.add(category)
            db.flush()
        category_map[item["slug"]] = category
    db.commit()

    created = 0
    for index, item in enumerate(PRODUCTS):
        data = dict(item)
        category_slug = data.pop("category")
        slug = data.pop("slug")
        price = money(data.pop("price"))
        is_available = data.pop("is_available", True)
        if db.scalar(select(Product).where(Product.slug == slug, Product.tenant_id == tenant_id)):
            continue
        product = Product(
            **data,
            tenant_id=tenant_id,
            slug=slug,
            category_id=category_map[category_slug].id,
            price=price,
            image_url=f"/assets/fish/{slug}.svg",
            gallery=[],
            sort_order=index * 10,
            is_active=True,
            is_available=is_available,
        )
        db.add(product)
        created += 1
    db.commit()
    if created:
        log.info("Добавлено товаров: %s", created)


def seed_all() -> None:
    db = SessionLocal()
    try:
        tenant = _seed_tenant(db)
        _seed_settings(db)
        admin = _seed_user(
            db,
            app_settings.admin_phone,
            app_settings.admin_password,
            app_settings.admin_name,
            ROLE_ADMIN,
        )
        if admin:
            log.info("Создан администратор %s", app_settings.admin_phone)
            if app_settings.is_production and app_settings.admin_password == "ChangeMe123!":
                log.warning("Смените пароль администратора по умолчанию!")

        if app_settings.seed_demo:
            # Демонстрационные аккаунты с известными паролями — только для разработки.
            _seed_user(db, "+375291112244", "Seller123!", "Продавец павильона", ROLE_SELLER)
            _seed_user(db, "+375291112255", "Customer123!", "Покупатель", ROLE_CUSTOMER)
        if app_settings.seed_catalog:
            if tenant:
                _seed_catalog(db, tenant.id)
            else:
                log.warning("Каталог не создан: нет арендатора по умолчанию")

        from app.platform.sync import ensure_tenant_services, sync_catalog

        sync_catalog(db)
        if tenant:
            ensure_tenant_services(db, tenant)
    finally:
        db.close()
