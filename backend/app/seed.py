"""Инициализация базы: платформа, арендаторы, пользователи и демо-каталог."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.db import SessionLocal
from app.defaults import build_defaults
from app.models import (
    DOMAIN_SUBDOMAIN,
    PLATFORM_OWNER,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_SELLER,
    TENANT_ACTIVE,
    Category,
    PlatformUser,
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


# ─── Демо-арендаторы других категорий ────────────────────────────────
# Нужны, чтобы платформа сразу показывала не только рыбный магазин.
DEMO_TENANTS = (
    {
        "slug": "flowers",
        "name": "Цветочная лавка",
        "preset": "flowers",
        "brand": "Цветочная лавка",
        "phone": "+375291112266",
        "owner": "Флорист",
        "categories": [
            {"slug": "bouquets", "title": "Букеты", "description": "Готовые букеты на любой повод."},
            {"slug": "plants", "title": "Комнатные растения", "description": "Растения для дома и офиса."},
        ],
        "products": [
            {
                "slug": "buket-pionov",
                "title": "Букет пионов",
                "category": "bouquets",
                "unit": "piece",
                "price": 85.00,
                "short_description": "Свежие пионы в крафтовой упаковке.",
                "description": "Сезонный букет из свежих пионов. Собираем утром под заказ.",
            },
            {
                "slug": "rozy-25",
                "title": "Розы, 25 шт.",
                "category": "bouquets",
                "unit": "piece",
                "price": 120.00,
                "short_description": "Классические розы 60 см.",
                "description": "Бордовые и белые розы, упаковка на выбор.",
            },
            {
                "slug": "monstera",
                "title": "Монстера",
                "category": "plants",
                "unit": "piece",
                "price": 45.00,
                "short_description": "Комнатное растение в горшке.",
                "description": "Молодая монстера высотой около 60 см.",
            },
        ],
    },
    {
        "slug": "meat",
        "name": "Мясная лавка",
        "preset": "meat",
        "brand": "Мясная лавка",
        "phone": "+375291112277",
        "owner": "Мясник",
        "categories": [
            {"slug": "beef", "title": "Говядина", "description": "Вырезка, лопатка, фарш."},
            {"slug": "poultry", "title": "Птица", "description": "Курица и индейка."},
        ],
        "products": [
            {
                "slug": "vyrezka-govyazhya",
                "title": "Вырезка говяжья",
                "category": "beef",
                "unit": "kg",
                "price": 42.00,
                "short_description": "Нежное мясо для стейков.",
                "description": "Охлаждённая вырезка, нарезаем по вашему запросу.",
            },
            {
                "slug": "kurinaya-grudka",
                "title": "Куриная грудка",
                "category": "poultry",
                "unit": "kg",
                "price": 14.50,
                "short_description": "Филе без кожи.",
                "description": "Охлаждённое филе куриной грудки.",
            },
        ],
    },
)


def _seed_settings(db: Session) -> None:
    if db.get(SiteSetting, 1):
        return
    db.add(SiteSetting(id=1, data=build_defaults()))
    db.commit()
    log.info("Настройки сайта созданы")


def _settings_for(brand: str) -> dict:
    data = build_defaults()
    data["brand_name"] = brand
    data["seo_title"] = brand
    return data


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
        name=app_settings.default_tenant_name,
        status=TENANT_ACTIVE,
        plan_code="start",
        category_preset="fish",
    )
    db.add(tenant)
    db.flush()
    db.add(TenantSettings(tenant_id=tenant.id, data=_settings_for(tenant.name)))
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


def _seed_platform_user(db: Session) -> PlatformUser | None:
    phone = app_settings.platform_admin_phone
    if db.scalar(select(PlatformUser).where(PlatformUser.phone == phone)):
        return None
    user = PlatformUser(
        phone=phone,
        full_name=app_settings.platform_admin_name,
        role=PLATFORM_OWNER,
        password_hash=hash_password(app_settings.platform_admin_password),
        is_phone_verified=True,
    )
    db.add(user)
    db.commit()
    log.info("Создан владелец платформы %s", phone)
    if app_settings.is_production and app_settings.platform_admin_password == "ChangeMe123!":
        log.warning("Смените пароль владельца платформы по умолчанию!")
    return user


def _seed_user(
    db: Session,
    tenant_id: int,
    phone: str,
    password: str,
    name: str,
    role: str,
) -> User | None:
    existing = db.scalar(
        select(User).where(User.phone == phone, User.tenant_id == tenant_id)
    )
    if existing:
        return None
    user = User(
        tenant_id=tenant_id,
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


def _seed_demo_tenant(db: Session, spec: dict, owner_phone: str) -> Tenant | None:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == spec["slug"]))
    if tenant:
        return tenant

    tenant = Tenant(
        slug=spec["slug"],
        name=spec["name"],
        status=TENANT_ACTIVE,
        plan_code="business",
        category_preset=spec["preset"],
        is_demo=True,
    )
    db.add(tenant)
    db.flush()
    db.add(TenantSettings(tenant_id=tenant.id, data=_settings_for(spec["brand"])))
    db.add(
        TenantDomain(
            tenant_id=tenant.id,
            host=f"{spec['slug']}.{app_settings.platform_base_domain}".lower(),
            kind=DOMAIN_SUBDOMAIN,
            is_primary=True,
            verified_at=utcnow(),
            ssl_status="pending",
            dns_status="ok",
        )
    )
    db.commit()

    categories: dict[str, Category] = {}
    for index, item in enumerate(spec["categories"]):
        category = Category(
            tenant_id=tenant.id,
            slug=item["slug"],
            title=item["title"],
            description=item["description"],
            sort_order=(index + 1) * 10,
            is_active=True,
        )
        db.add(category)
        db.flush()
        categories[item["slug"]] = category

    for index, item in enumerate(spec["products"]):
        db.add(
            Product(
                tenant_id=tenant.id,
                slug=item["slug"],
                title=item["title"],
                subtitle=item.get("subtitle", ""),
                category_id=categories[item["category"]].id,
                unit=item["unit"],
                price=money(item["price"]),
                discount_percent=0,
                is_daily_deal=False,
                is_available=True,
                is_active=True,
                stock=None,
                weight_note="",
                image_url=None,
                gallery=[],
                badges=[],
                short_description=item["short_description"],
                description=item["description"],
                origin="",
                season="",
                nutrition={},
                cooking_tips="",
                storage_tips="",
                sort_order=(index + 1) * 10,
            )
        )
    db.commit()

    _seed_user(db, tenant.id, owner_phone, "ChangeMe123!", spec["owner"], ROLE_ADMIN)
    log.info("Создан демо-арендатор: %s", spec["slug"])
    return tenant


def seed_all() -> None:
    db = SessionLocal()
    try:
        _seed_platform_user(db)
        tenant = _seed_tenant(db)
        _seed_settings(db)

        admin = None
        if tenant:
            admin = _seed_user(
                db,
                tenant.id,
                app_settings.admin_phone,
                app_settings.admin_password,
                app_settings.admin_name,
                ROLE_ADMIN,
            )
        if admin:
            log.info("Создан администратор магазина %s", app_settings.admin_phone)
            if app_settings.is_production and app_settings.admin_password == "ChangeMe123!":
                log.warning("Смените пароль администратора по умолчанию!")

        tenants: list[Tenant] = [tenant] if tenant else []
        if app_settings.seed_demo and tenant:
            # Демонстрационные аккаунты с известными паролями — только для разработки.
            _seed_user(db, tenant.id, "+375291112244", "Seller123!", "Продавец павильона", ROLE_SELLER)
            _seed_user(db, tenant.id, "+375291112255", "Customer123!", "Покупатель", ROLE_CUSTOMER)
            for spec in DEMO_TENANTS:
                demo = _seed_demo_tenant(db, spec, spec["phone"])
                if demo:
                    tenants.append(demo)

        if app_settings.seed_catalog and tenant:
            _seed_catalog(db, tenant.id)

        from app.platform.sync import ensure_tenant_services, sync_catalog

        sync_catalog(db)
        for item in tenants:
            ensure_tenant_services(db, item)
    finally:
        db.close()
