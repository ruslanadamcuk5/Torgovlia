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
    DeliveryZone,
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
    {
        "slug": "odezhda",
        "name": "Модная лавка",
        "preset": "clothing",
        "brand": "Модная лавка",
        "phone": "+375291112288",
        "owner": "Стилист",
        "categories": [
            {"slug": "verhnyaya-odezhda", "title": "Верхняя одежда", "description": "Куртки, пальто, тренчи."},
            {"slug": "tricotazh", "title": "Трикотаж", "description": "Худи, футболки, свитшоты."},
        ],
        "products": [
            {
                "slug": "bomber",
                "title": "Куртка-бомбер",
                "category": "verhnyaya-odezhda",
                "unit": "piece",
                "price": 189.00,
                "short_description": "Плотная ткань, свободный крой.",
                "description": "Бомбер на всесезонье, размеры S–XL. Примерка в павильоне.",
            },
            {
                "slug": "trench",
                "title": "Тренч классический",
                "category": "verhnyaya-odezhda",
                "unit": "piece",
                "price": 249.00,
                "short_description": "Двубортный тренч с поясом.",
                "description": "Классический тренч песочного цвета, размеры 42–50.",
            },
            {
                "slug": "hudi",
                "title": "Худи оверсайз",
                "category": "tricotazh",
                "unit": "piece",
                "price": 79.00,
                "short_description": "Мягкий футер, базовый цвет.",
                "description": "Худи свободного кроя из плотного футера, размеры S–XL.",
            },
        ],
    },
)


# ─── Оформление демо-арендаторов ─────────────────────────────────────
# Тексты и блоки витрины под конкретную категорию. Применяются к демо-сайтам,
# чтобы цветочная и мясная лавки не выглядели копией рыбной.
DEMO_BRANDING = {
    "flowers": {
        "tagline": "Свежие цветы и композиции",
        "hero_badge": "Цветы и растения · Барановичи",
        "hero_title": "Букеты, которые говорят за вас",
        "hero_subtitle": (
            "Свежие цветы, сезонные композиции и комнатные растения в павильоне "
            "на рынке «Алексеевский». Забронируйте онлайн — соберём к вашему приходу."
        ),
        "announcement": "Пионы, розы и сезонные букеты — сборка в день заказа.",
        "address": "г. Барановичи, ул. Комсомольская, 45, рынок «Алексеевский», павильон 8",
        "legal_address": "г. Барановичи, ул. Комсомольская, 45",
        "pavilion": "павильон 8",
        "email": "info@flower-lavka.by",
        "phone": "+375 29 111-22-66",
        "socials": {
            "instagram": "https://www.instagram.com/flowers.lavka",
            "tiktok": "https://www.tiktok.com/@flowers.lavka",
            "telegram": "https://t.me/flowers_lavka",
        },
        "about_text": (
            "«Цветочная лавка» — семейный павильон на рынке «Алексеевский» в Барановичах. "
            "Мы собираем букеты каждый день: принимаем свежие поставки, проверяем качество "
            "стеблей и держим цветы в прохладе до момента продажи.\n\n"
            "В ассортименте — готовые букеты, монокомпозиции, сезонные цветы и комнатные "
            "растения. Если нужен особый повод, соберём композицию под ваш бюджет и настроение.\n\n"
            "Забронировать букет можно на сайте или в мобильном приложении. Вы выбираете "
            "композицию и удобное время — мы собираем заказ и ждём вас в павильоне. "
            "Оплата при получении: наличными или картой."
        ),
        "advantages": [
            ("leaf", "Свежие поставки", "Цветы приезжают дважды в неделю и хранятся в прохладе до продажи."),
            ("gift", "Сборка под повод", "Подберём композицию под бюджет, повод и ваши пожелания."),
            ("clock", "Бронь за минуту", "Выберите букет и время. Оплата при получении — без предоплаты."),
            ("shield", "Гарантия свежести", "Если цветок не доживёт до вечера — заменим или вернём деньги."),
        ],
        "banners": [
            ("Сезонные букеты каждую неделю", "Пионы, тюльпаны и розы — свежая поставка к открытию павильона."),
            ("Соберём букет под ваш повод", "Расскажите о поводе и бюджете — предложим готовую композицию."),
        ],
        "category_noun": "цветы",
        "storage_note": "Цветы — товар ограниченного срока годности.",
    },
    "meat": {
        "tagline": "Свежее мясо и птица",
        "hero_badge": "Мясо и птица · Барановичи",
        "hero_title": "Мясо с фермы — без посредников",
        "hero_subtitle": (
            "Охлаждённая говядина, свинина и птица в павильоне на рынке "
            "«Алексеевский». Забронируйте онлайн — подготовим к вашему приходу."
        ),
        "announcement": "Свежая вырезка и домашняя птица — каждый день с 8:00.",
        "address": "г. Барановичи, ул. Комсомольская, 45, рынок «Алексеевский», павильон 15",
        "legal_address": "г. Барановичи, ул. Комсомольская, 45",
        "pavilion": "павильон 15",
        "email": "info@myasnaya-lavka.by",
        "phone": "+375 29 111-22-77",
        "socials": {
            "instagram": "https://www.instagram.com/meat.lavka",
            "tiktok": "https://www.tiktok.com/@meat.lavka",
            "telegram": "https://t.me/meat_lavka",
        },
        "about_text": (
            "«Мясная лавка» — семейный павильон на рынке «Алексеевский» в Барановичах. "
            "Мы работаем с мясом каждый день: принимаем охлаждённые поставки, проверяем "
            "документы и разделываем небольшими партиями под заказ.\n\n"
            "В ассортименте — говядина, свинина, домашняя птица и полуфабрикаты. "
            "Подскажем, какая часть подойдёт для стейка, тушения или фарша.\n\n"
            "Забронировать товар можно на сайте или в мобильном приложении. Вы выбираете "
            "мясо, вес и удобное время — мы готовим заказ и ждём вас в павильоне. "
            "Оплата при получении: наличными или картой."
        ),
        "advantages": [
            ("shield", "Документы и контроль", "Ветеринарные документы и контроль температуры на каждой поставке."),
            ("scissors", "Разделка на месте", "Нарежем, почистим и упакуем так, как нужно для вашего блюда."),
            ("clock", "Бронь за минуту", "Выберите товар и время. Оплата при получении — без предоплаты."),
            ("leaf", "Свежее, не замороженное", "Работаем с охлаждённым мясом и снимаем остатки с продажи в тот же день."),
        ],
        "banners": [
            ("Свежая вырезка по вторникам и пятницам", "Охлаждённая говядина и птица — прямо к открытию павильона."),
            ("Забронируйте — и не стойте в очереди", "Выберите мясо, вес и время. Подготовим заказ к вашему приходу."),
        ],
        "category_noun": "мясо",
        "storage_note": "Мясо — скоропортящийся товар.",
    },
    "clothing": {
        "tagline": "Одежда на каждый день",
        "hero_badge": "Одежда и трикотаж · Барановичи",
        "hero_title": "Базовый гардероб без переплат",
        "hero_subtitle": (
            "Женская и мужская одежда, трикотаж и верхняя одежда в павильоне "
            "на рынке «Алексеевский». Забронируйте онлайн — отложим нужный размер."
        ),
        "announcement": "Новая коллекция трикотажа — примерка и бронь в павильоне.",
        "address": "г. Барановичи, ул. Комсомольская, 45, рынок «Алексеевский», павильон 21",
        "legal_address": "г. Барановичи, ул. Комсомольская, 45",
        "pavilion": "павильон 21",
        "email": "info@modnaya-lavka.by",
        "phone": "+375 29 111-22-88",
        "socials": {
            "instagram": "https://www.instagram.com/modnaya.lavka",
            "tiktok": "https://www.tiktok.com/@modnaya.lavka",
            "telegram": "https://t.me/modnaya_lavka",
        },
        "about_text": (
            "«Модная лавка» — павильон одежды на рынке «Алексеевский» в Барановичах. "
            "Мы собираем базовый гардероб на каждый день: верхнюю одежду, трикотаж "
            "и вещи, которые легко сочетать между собой.\n\n"
            "В ассортименте — куртки и тренчи, худи и футболки, размеры S–XL. "
            "Поможем подобрать посадку и цвет, покажем, что есть в наличии.\n\n"
            "Забронировать вещь можно на сайте или в мобильном приложении. Вы выбираете "
            "модель и размер — мы откладываем её в павильоне. Примерка и оплата при получении."
        ),
        "advantages": [
            ("shirt", "Размеры в наличии", "S–XL в павильоне: подскажем посадку и поможем с выбором."),
            ("tag", "Честные цены", "Без наценки за бренд: цена на сайте совпадает с ценником."),
            ("clock", "Бронь за минуту", "Выберите модель и размер. Оплата при получении — без предоплаты."),
            ("refresh", "Обмен в день покупки", "Не подошёл размер — обменяем на другой в тот же день."),
        ],
        "banners": [
            ("Новый трикотаж каждую неделю", "Худи, свитшоты и футболки — свежие цвета и размеры."),
            ("Забронируйте нужный размер", "Выберите модель онлайн — отложим её к вашему приходу."),
        ],
        "category_noun": "одежда",
        "storage_note": "Бронь одежды держим 2 часа после выбранного времени.",
    },
}


def _demo_pickup_rules(noun: str, storage_note: str) -> str:
    return f"""## Как работает бронирование

Бронирование — это бесплатное резервирование {noun} к вашему приходу. Доставка не осуществляется: заказ необходимо забрать в павильоне на рынке «Алексеевский».

## Порядок действий

1. Выберите товары в каталоге и укажите нужное количество или вес.
2. Укажите дату и время, когда вам удобно забрать заказ.
3. Подтвердите номер мобильного телефона кодом из SMS.
4. Мы соберём заказ и пришлём подтверждение. Заказ хранится до указанного времени.

## Важно

• Минимальная сумма брони — {{min_order}}. Стоимость рассчитывается по фактическому весу или количеству и корректируется при выдаче.
• {storage_note} Заказ, который не забрали в течение 2 часов после выбранного времени, может быть отменён.
• Наличие товара обновляется продавцом в течение дня. Если позиция закончилась, мы свяжемся с вами и предложим замену или отменим бронь.
• Оплата производится в павильоне при получении: наличными или банковской картой.
• Отказаться от заказа можно в личном кабинете или по телефону павильона до начала сборки.

## Персональные данные

Оформляя бронь, вы соглашаетесь с обработкой персональных данных в целях исполнения заказа в соответствии с Законом Республики Беларусь от 07.05.2021 № 99-З «О защите персональных данных»."""


def _demo_overrides(preset: str | None) -> dict:
    branding = DEMO_BRANDING.get(preset or "")
    if not branding:
        return {}
    from app.defaults import PRIVACY_POLICY
    from app.schemas import Advantage, Banner, Socials

    return {
        "tagline": branding["tagline"],
        "hero_badge": branding["hero_badge"],
        "hero_title": branding["hero_title"],
        "hero_subtitle": branding["hero_subtitle"],
        "announcement": branding["announcement"],
        "announcement_active": True,
        "address": branding["address"],
        "legal_address": branding["legal_address"],
        "pavilion": branding["pavilion"],
        "email": branding["email"],
        "phone": branding["phone"],
        "socials": Socials(**branding["socials"]).model_dump(),
        "about_text": branding["about_text"],
        "pickup_rules": _demo_pickup_rules(
            branding["category_noun"],
            branding["storage_note"],
        ),
        "privacy_policy": PRIVACY_POLICY.replace("«Рыбная лавка»", "магазина"),
        "advantages": [
            Advantage(icon=icon, title=title, text=text).model_dump()
            for icon, title, text in branding["advantages"]
        ],
        "banners": [
            Banner(id=f"b{index}", title=title, subtitle=subtitle).model_dump()
            for index, (title, subtitle) in enumerate(branding["banners"], start=1)
        ],
    }


def _settings_for(brand: str, preset: str | None = None) -> dict:
    data = build_defaults()
    data["brand_name"] = brand
    data["seo_title"] = brand
    data.update(_demo_overrides(preset))
    from app.platform.templates import default_template_for

    data["template"] = default_template_for(preset)
    return data


def _polish_demo_settings(db: Session, tenant: Tenant, spec: dict) -> None:
    """Обновляет демо-оформление, не затирая ручные правки владельца."""
    row = db.get(TenantSettings, tenant.id)
    if row is None:
        db.add(TenantSettings(tenant_id=tenant.id, data=_settings_for(spec["brand"], spec["preset"])))
        db.commit()
        return
    base = build_defaults()
    data = dict(row.data or {})
    changed = False
    if "template" not in data:
        from app.platform.templates import default_template_for

        data["template"] = default_template_for(spec["preset"])
        changed = True
    for key, value in _demo_overrides(spec["preset"]).items():
        current = data.get(key)
        if key not in data or current == base.get(key):
            data[key] = value
            changed = True
    if changed:
        row.data = data
        db.add(row)
        db.commit()
        log.info("Демо-оформление обновлено: %s", tenant.slug)


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
    email: str | None = None,
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
        email=email,
        role=role,
        password_hash=hash_password(password),
        is_phone_verified=True,
        consent_personal_data=True,
    )
    db.add(user)
    db.commit()
    return user


DEMO_CUSTOMERS = (
    ("+375291113301", "Анна Ковалёва", "anna@example.by"),
    ("+375291113302", "Сергей Петров", "sergey@example.by"),
    ("+375291113303", "Мария Иванова", "maria@example.by"),
    ("+375291113304", "Дмитрий Сидоров", "dmitry@example.by"),
    ("+375291113305", "Елена Морозова", "elena@example.by"),
    ("+375291113306", "Ольга Новикова", "olga@example.by"),
)


def _seed_demo_customers(db: Session, tenant_id: int) -> None:
    """Клиенты с почтой и телефоном, чтобы демо-рассылки было на ком показывать."""
    for phone, name, email in DEMO_CUSTOMERS:
        _seed_user(db, tenant_id, phone, "Customer123!", name, ROLE_CUSTOMER, email=email)


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


def _seed_delivery_zones(db: Session, tenant: Tenant) -> None:
    """Демо-зоны доставки, чтобы витрина сразу показывала сценарий."""
    exists = db.scalar(
        select(DeliveryZone.id).where(DeliveryZone.tenant_id == tenant.id).limit(1)
    )
    if exists:
        return
    db.add_all(
        [
            DeliveryZone(
                tenant_id=tenant.id,
                name="Барановичи",
                areas="г. Барановичи",
                fee=money(5),
                min_order=money(20),
                free_from=money(80),
                eta="1–2 часа",
                is_active=True,
                sort_order=10,
            ),
            DeliveryZone(
                tenant_id=tenant.id,
                name="Барановичский район",
                areas="деревни и агрогородки района",
                fee=money(10),
                min_order=money(30),
                free_from=money(150),
                eta="на следующий день",
                is_active=True,
                sort_order=20,
            ),
        ]
    )
    db.commit()
    log.info("Добавлены демо-зоны доставки: %s", tenant.slug)


def _seed_demo_tenant(db: Session, spec: dict, owner_phone: str) -> Tenant | None:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == spec["slug"]))
    if tenant:
        _polish_demo_settings(db, tenant, spec)
        _seed_delivery_zones(db, tenant)
        _seed_demo_customers(db, tenant.id)
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
    db.add(TenantSettings(tenant_id=tenant.id, data=_settings_for(spec["brand"], spec["preset"])))
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
    _seed_demo_customers(db, tenant.id)
    _seed_delivery_zones(db, tenant)
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
                    if spec["slug"] == "odezhda" and app_settings.demo_content:
                        from app.demo_odezhda import enrich

                        enrich(db, demo)

        if app_settings.seed_catalog and tenant:
            _seed_catalog(db, tenant.id)

        from app.platform.entitlements import enable as enable_service
        from app.platform.sync import ensure_tenant_services, sync_catalog

        sync_catalog(db)
        for item in tenants:
            ensure_tenant_services(db, item)
            # Демо-витрины сразу показывают промокоды: сервис включён, но
            # остаётся выключенным по умолчанию для реальных арендаторов.
            if item.is_demo and item.plan_code in ("business", "pro"):
                for service_code in ("promo_codes", "reviews", "delivery", "price_tags", "barcode", "labels"):
                    try:
                        enable_service(db, item, service_code)
                    except Exception as exc:  # noqa: BLE001 — демо не должно ронять старт
                        db.rollback()
                        log.warning(
                            "Не удалось включить %s для %s: %s", service_code, item.slug, exc
                        )
            if item.is_demo:
                # Демо-стенд показывает и услуги тарифа Про, иначе их не оценить.
                try:
                    from app.platform.entitlements import platform_update

                    for service_code in (
                        "price_import",
                        "email_marketing",
                        "sms_marketing",
                        "segments",
                        "crm",
                        "abandoned_cart",
                        "upsell",
                        "loyalty",
                        "support_chat",
                        "tasks",
                        "gift_certificates",
                    ):
                        platform_update(db, item, service_code, status_value="enabled")
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    log.warning("Не удалось включить демо-услуги для %s: %s", item.slug, exc)
    finally:
        db.close()
