"""Полное наполнение флагманского демо-магазина «Модная лавка».

Демо должно показывать не пустой каркас, а работающий магазин: категории,
товары с фото и штрихкодами, склад, поставщиков, закупки, заказы, отзывы,
промокоды, бонусы, клиентов, корзины, рассылки и переписку. Всё создаётся
идемпотентно: повторный запуск дополняет недостающее и не дублирует записи.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ORDER_CANCELLED,
    ORDER_COMPLETED,
    ORDER_CONFIRMED,
    ORDER_NEW,
    ORDER_READY,
    ORDER_REJECTED,
    REVIEW_PUBLISHED,
    ROLE_CUSTOMER,
    TASK_CANCELLED,
    TASK_DONE,
    TASK_IN_PROGRESS,
    TASK_TODO,
    Campaign,
    CampaignRecipient,
    Cart,
    Category,
    ChatMessage,
    ChatThread,
    CustomerNote,
    CustomerTag,
    LoyaltyAccount,
    LoyaltySettings,
    LoyaltyTransaction,
    Order,
    OrderItem,
    Product,
    PromoCode,
    PurchaseItem,
    PurchaseOrder,
    Review,
    StaffTask,
    StockMovement,
    Supplier,
    Tenant,
    UpsellRule,
    User,
)
from app.services import barcode as barcode_service
from app.utils import money, qty


log = logging.getLogger("torgovlia.demo")

CATEGORIES = (
    ("verhnyaya-odezhda", "Верхняя одежда", "Куртки, пальто и тренчи на каждый день."),
    ("tricotazh", "Трикотаж", "Худи, свитшоты и футболки из плотного хлопка."),
    ("rubashki", "Рубашки и блузы", "Рубашки оверсайз и блузы для офиса и встреч."),
    ("bryuki", "Брюки и джинсы", "Прямые джинсы и классические брюки."),
    ("platya", "Платья и юбки", "Платья миди и юбки в складку."),
    ("aksessuary", "Аксессуары", "Шарфы, сумки и детали, которые дополняют образ."),
    ("obuv", "Обувь", "Кроссовки и ботинки на каждый день."),
)

# slug, название, категория, цена, скидка %, остаток, бейдж, короткое и полное описание
PRODUCTS = (
    (
        "bomber", "Куртка-бомбер", "verhnyaya-odezhda", 189, 15, 12, "Хит",
        "Плотная ткань, свободный крой.",
        "Бомбер из плотной курточной ткани с мягкой подкладкой. Свободный крой не "
        "сковывает движения, резинка по низу держит форму. Подходит для межсезонья: "
        "надевается поверх худи или рубашки.\n\nРазмеры S–XL. Примерка в павильоне, "
        "обмен размера в день покупки.",
    ),
    (
        "trench", "Тренч классический", "verhnyaya-odezhda", 249, 0, 7, "Новинка",
        "Двубортный тренч с поясом.",
        "Классический двубортный тренч песочного цвета с поясом и глубокими карманами. "
        "Ткань держит форму и не боится городской погоды. Длина ниже колена.\n\n"
        "Размеры 42–50. В комплекте съёмный пояс.",
    ),
    (
        "palto", "Пальто шерстяное", "verhnyaya-odezhda", 349, 10, 5, "",
        "Тёплое пальто прямого кроя.",
        "Пальто из шерстяной смеси прямого кроя с воротником-стойкой. Держит тепло "
        "в прохладную погоду и легко сочетается с джинсами и платьем.\n\n"
        "Размеры S–XL, два цвета: кэмел и графит.",
    ),
    (
        "hudi", "Худи оверсайз", "tricotazh", 79, 0, 34, "Хит",
        "Мягкий футер, базовый цвет.",
        "Худи свободного кроя из плотного футера с начёсом. Широкий капюшон, "
        "карман-кенгуру и мягкие манжеты. Базовый серый цвет сочетается с любым низом.\n\n"
        "Размеры S–XL. Стирка при 30 °C, без отжима.",
    ),
    (
        "svitshot", "Свитшот с вышивкой", "tricotazh", 89, 20, 18, "Скидка",
        "Кремовый свитшот, маленькая вышивка.",
        "Свитшот из мягкого хлопка с небольшой вышивкой на груди. Кремовый цвет, "
        "круглый ворот и широкие манжеты. Универсальная вещь для повседневного гардероба.\n\n"
        "Размеры S–XL. Не линяет при стирке.",
    ),
    (
        "futbolka", "Футболка базовая", "tricotazh", 39, 0, 46, "",
        "Плотный хлопок 100%.",
        "Базовая белая футболка из плотного хлопка. Прямой крой, аккуратная горловина, "
        "не просвечивает. Отличная база под пиджак, рубашку или куртку.\n\n"
        "Размеры S–XL. Есть в белом, чёрном и графитовом цвете.",
    ),
    (
        "rubashka", "Рубашка оверсайз", "rubashki", 119, 0, 22, "Новинка",
        "Голубая рубашка свободного кроя.",
        "Рубашка из мягкого хлопка свободного кроя. Голубой цвет, накладной карман, "
        "пуговицы в тон. Носится и навыпуск, и заправленной.\n\n"
        "Размеры S–XL. Гладится легко, не садится после стирки.",
    ),
    (
        "bluza", "Блуза с бантом", "rubashki", 129, 15, 9, "",
        "Элегантная блуза для офиса.",
        "Блуза с мягким бантом у горловины и длинным рукавом. Струящаяся ткань "
        "приятна к телу, подходит для офиса и встреч.\n\n"
        "Размеры S–XL. Рекомендуется деликатная стирка.",
    ),
    (
        "dzhinsy", "Джинсы прямые", "bryuki", 159, 0, 26, "Хит",
        "Классические синие джинсы.",
        "Прямые джинсы средней посадки из плотного денима. Классический синий цвет, "
        "пять карманов, аккуратная строчка. Не тянутся, держат форму.\n\n"
        "Размеры 26–34. Подскажем посадку в павильоне.",
    ),
    (
        "bryuki", "Брюки со стрелками", "bryuki", 139, 10, 14, "",
        "Графитовые брюки с защипами.",
        "Классические брюки со стрелками и мягкими защипами. Графитовый цвет, "
        "прямой крой, удобная посадка. Подходят для работы и вечера.\n\n"
        "Размеры 42–50. Ткань с небольшим добавлением эластана.",
    ),
    (
        "platye", "Платье миди", "platya", 219, 0, 10, "Новинка",
        "Изумрудное платье миди.",
        "Платье миди из струящейся ткани глубокого изумрудного цвета. Приталенный "
        "силуэт, мягкая юбка, аккуратный вырез. Для праздника и повседневных выходов.\n\n"
        "Размеры S–XL. В комплекте съёмный пояс.",
    ),
    (
        "yubka", "Юбка плиссе", "platya", 119, 20, 16, "Скидка",
        "Бежевая юбка в мелкую складку.",
        "Юбка миди в мелкую складку из лёгкой ткани. Бежевый цвет, мягкая резинка "
        "на поясе. Хорошо смотрится с футболкой, свитшотом и рубашкой.\n\n"
        "Размеры S–XL. Не требует глажки.",
    ),
    (
        "sharf", "Шарф крупной вязки", "aksessuary", 59, 0, 28, "",
        "Объёмный шарф овсяного цвета.",
        "Шарф крупной вязки из мягкой пряжи. Овсяный цвет подходит к верхней одежде "
        "любого оттенка. Длина достаточная, чтобы укутаться в ветреный день.\n\n"
        "Один размер. Ручная стирка при 30 °C.",
    ),
    (
        "sumka", "Сумка-шоппер", "aksessuary", 99, 10, 20, "",
        "Кожаная сумка на каждый день.",
        "Сумка-шоппер из плотной кожи с двумя ручками. Внутри — карман для телефона "
        "и мелочей. Вмещает ноутбук 13 дюймов и папку с документами.\n\n"
        "Один размер. Цвет — коньячный.",
    ),
    (
        "krossovki", "Кроссовки белые", "obuv", 179, 0, 15, "Хит",
        "Минималистичные кожаные кроссовки.",
        "Белые кожаные кроссовки на мягкой подошве. Минималистичный дизайн, "
        "подходят к джинсам, брюкам и платью. Стелька съёмная.\n\n"
        "Размеры 36–44. Уход — влажная салфетка.",
    ),
    (
        "botinki", "Ботинки кожаные", "obuv", 229, 15, 8, "",
        "Тёмно-коричневые ботинки на шнуровке.",
        "Ботинки из натуральной кожи на устойчивой подошве. Тёмно-коричневый цвет, "
        "шнуровка, мягкая подкладка. Для осени и мягкой зимы.\n\n"
        "Размеры 37–45. Рекомендуется обработка водоотталкивающим средством.",
    ),
)

SUPPLIERS = (
    ("ООО «БелТекстиль»", "Ирина Лебедева", "+375 17 200-11-45", "sales@beltextil.by", "Минск, ул. Тимирязева, 65", "Трикотаж и базовые модели, отсрочка 14 дней."),
    ("ИП Ковальчук", "Андрей Ковальчук", "+375 29 344-18-90", "kovalchuk@mail.by", "Барановичи, ул. Советская, 12", "Верхняя одежда и обувь, поставка раз в неделю."),
    ("Fashion Hub", "Ольга Смирнова", "+375 33 610-22-77", "order@fashionhub.by", "Минск, пр-т Победителей, 106", "Аксессуары и демисезонные коллекции."),
)

REVIEWS = (
    ("hudi", "Анна К.", 5, "Очень мягкое худи, размер совпал. Забрала в тот же день, как забронировала.", True),
    ("dzhinsy", "Сергей П.", 5, "Плотный деним, не тянутся. Помогли выбрать посадку в павильоне.", True),
    ("bomber", "Мария И.", 4, "Куртка отличная, но хотелось бы больше расцветок. Качество на высоте.", True),
    ("futbolka", "Дмитрий С.", 5, "Базовая футболка, держит форму после стирок. Взял ещё две.", True),
    ("platye", "Елена М.", 5, "Платье село идеально, ткань струится. На празднике все спрашивали, где брала.", True),
    ("krossovki", "Ольга Н.", 4, "Удобные, но лучше брать на полразмера больше. Обменяли без вопросов.", True),
    ("sharf", "Анна К.", 5, "Тёплый и мягкий, цвет точно как на фото.", False),
    ("sumka", "Сергей П.", 5, "Вмещает ноутбук и папку, выглядит дорого. Пользуюсь каждый день.", True),
)

DEMO_NOTES = (
    ("+375291113301", "Постоянная клиентка, любит трикотаж. Напомнить о новой поставке худи."),
    ("+375291113302", "Покупает верхнюю одежду, размер L. Уточнять наличие перед поставкой."),
    ("+375291113305", "Просила отложить платье на выходные, звонить за день."),
)

DEMO_TAGS = (
    ("+375291113301", "VIP"),
    ("+375291113301", "трикотаж"),
    ("+375291113302", "верхняя одежда"),
    ("+375291113305", "платья"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
    return _now() - timedelta(days=days, hours=hours, minutes=minutes)


def _phone(tenant_id: int, db: Session, phone: str) -> User | None:
    return db.scalar(select(User).where(User.tenant_id == tenant_id, User.phone == phone))


def _upsert_categories(db: Session, tenant: Tenant) -> dict[str, Category]:
    result: dict[str, Category] = {}
    for index, (slug, title, description) in enumerate(CATEGORIES):
        row = db.scalar(
            select(Category).where(Category.tenant_id == tenant.id, Category.slug == slug)
        )
        if row is None:
            row = Category(tenant_id=tenant.id, slug=slug)
            db.add(row)
        row.title = title
        row.description = description
        row.sort_order = (index + 1) * 10
        row.is_active = True
        db.flush()
        result[slug] = row
    db.commit()
    return result


def _upsert_products(db: Session, tenant: Tenant, categories: dict[str, Category]) -> dict[str, Product]:
    result: dict[str, Product] = {}
    for index, item in enumerate(PRODUCTS):
        (
            slug,
            title,
            category_slug,
            price,
            discount,
            stock,
            badge,
            short,
            description,
        ) = item
        row = db.scalar(
            select(Product).where(Product.tenant_id == tenant.id, Product.slug == slug)
        )
        if row is None:
            row = Product(tenant_id=tenant.id, slug=slug)
            db.add(row)
        row.title = title
        row.subtitle = short
        row.category_id = categories[category_slug].id
        row.unit = "piece"
        row.price = money(price)
        row.discount_percent = int(discount)
        row.is_daily_deal = slug == "svitshot"
        row.is_available = True
        row.is_active = True
        row.stock = qty(stock)
        row.weight_note = "S–XL" if category_slug not in ("obuv", "aksessuary") else ""
        row.image_url = f"/assets/demo/odezhda/{slug}.svg"
        row.gallery = []
        row.badges = [badge] if badge else []
        row.short_description = short
        row.description = description
        row.origin = "Беларусь"
        row.season = "круглый год"
        row.nutrition = {}
        row.cooking_tips = "Стирка при 30 °C, не отбеливать, гладить при средней температуре."
        row.storage_tips = "Хранить на вешалке или в сложенном виде в сухом месте."
        row.sort_order = (index + 1) * 10
        db.flush()
        if not row.barcode:
            barcode_service.assign_default(db, row)
        result[slug] = row
    db.commit()
    return result


def _seed_suppliers(db: Session, tenant: Tenant) -> list[Supplier]:
    if db.scalar(select(func.count(Supplier.id)).where(Supplier.tenant_id == tenant.id)):
        return list(db.scalars(select(Supplier).where(Supplier.tenant_id == tenant.id)).all())
    rows = []
    for name, contact, phone, email, address, note in SUPPLIERS:
        rows.append(
            Supplier(
                tenant_id=tenant.id,
                name=name,
                contact_person=contact,
                phone=phone,
                email=email,
                address=address,
                note=note,
                is_active=True,
            )
        )
    db.add_all(rows)
    db.commit()
    return rows


def _seed_purchases(db: Session, tenant: Tenant, suppliers: list[Supplier], products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.tenant_id == tenant.id)) or not suppliers:
        return
    plans = (
        (suppliers[0], "PO-1001", "received", ("hudi", "futbolka", "svitshot")),
        (suppliers[1], "PO-1002", "ordered", ("bomber", "botinki")),
        (suppliers[2], "PO-1003", "draft", ("sharf", "sumka")),
    )
    for index, (supplier, number, status, slugs) in enumerate(plans):
        order = PurchaseOrder(
            tenant_id=tenant.id,
            number=number,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            status=status,
            expected_date=(_now() + timedelta(days=3 + index * 2)).date(),
            note="Демо-закупка для проверки склада и приёмки." if status != "received" else "Принято полностью.",
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        db.flush()
        total = Decimal("0.00")
        for slug in slugs:
            product = products.get(slug)
            if not product:
                continue
            quantity = qty(3 if status == "draft" else 6)
            cost = money(product.price * Decimal("0.55"))
            line = line_total = money(cost * quantity)
            total += line
            db.add(
                PurchaseItem(
                    tenant_id=tenant.id,
                    purchase_id=order.id,
                    product_id=product.id,
                    title=product.title,
                    unit=product.unit,
                    quantity=quantity,
                    cost=cost,
                    line_total=line_total,
                )
            )
        order.total_amount = money(total)
        if status == "received":
            order.received_at = _ago(days=6)
    db.commit()


def _seed_stock(db: Session, tenant: Tenant, products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(StockMovement.id)).where(StockMovement.tenant_id == tenant.id)):
        return
    samples = (
        ("hudi", "in", 12, "Поставка «БелТекстиль», PO-1001"),
        ("dzhinsy", "in", 8, "Поставка денима"),
        ("krossovki", "out", 3, "Продажа, заказ №1042"),
        ("bomber", "out", 2, "Продажа, заказ №1038"),
        ("platye", "adjust", -1, "Инвентаризация: повреждение упаковки"),
    )
    for slug, kind, quantity, reason in samples:
        product = products.get(slug)
        if not product:
            continue
        before = product.stock or Decimal("0")
        after = before + qty(quantity) if kind == "in" else before - qty(abs(quantity))
        db.add(
            StockMovement(
                tenant_id=tenant.id,
                product_id=product.id,
                product_title=product.title,
                kind=kind,
                quantity=qty(quantity),
                stock_before=before,
                stock_after=max(Decimal("0"), after),
                reason=reason,
                actor="Стилист",
                created_at=_ago(days=5),
            )
        )
    db.commit()


def _seed_promos(db: Session, tenant: Tenant) -> None:
    if db.scalar(select(func.count(PromoCode.id)).where(PromoCode.tenant_id == tenant.id)):
        return
    db.add_all(
        [
            PromoCode(
                tenant_id=tenant.id,
                code="WELCOME10",
                kind="percent",
                value=money(10),
                min_order=money(80),
                max_uses=0,
                used_count=14,
                note="Скидка новым покупателям на первый заказ.",
                is_active=True,
            ),
            PromoCode(
                tenant_id=tenant.id,
                code="TRICOT15",
                kind="percent",
                value=money(15),
                min_order=money(120),
                max_uses=100,
                used_count=6,
                note="Неделя трикотажа: скидка на худи и свитшоты.",
                is_active=True,
            ),
            PromoCode(
                tenant_id=tenant.id,
                code="PICKUP5",
                kind="fixed",
                value=money(5),
                min_order=money(60),
                max_uses=0,
                used_count=23,
                note="Скидка за самовывоз из павильона.",
                is_active=True,
            ),
        ]
    )
    db.commit()


def _seed_reviews(db: Session, tenant: Tenant, products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(Review.id)).where(Review.tenant_id == tenant.id)):
        return
    for index, (slug, name, rating, text, verified) in enumerate(REVIEWS):
        product = products.get(slug)
        if not product:
            continue
        db.add(
            Review(
                tenant_id=tenant.id,
                product_id=product.id,
                customer_name=name,
                rating=rating,
                text=text,
                status=REVIEW_PUBLISHED,
                is_verified_purchase=verified,
                published_at=_ago(days=2 + index * 2),
                created_at=_ago(days=3 + index * 2),
            )
        )
    db.commit()


def _seed_orders(db: Session, tenant: Tenant, products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(Order.id)).where(Order.tenant_id == tenant.id)):
        return
    customers = (
        ("+375291113301", "Анна Ковалёва"),
        ("+375291113302", "Сергей Петров"),
        ("+375291113303", "Мария Иванова"),
        ("+375291113304", "Дмитрий Сидоров"),
        ("+375291113305", "Елена Морозова"),
        ("+375291113306", "Ольга Новикова"),
    )
    plans = (
        ("1041", 0, ORDER_COMPLETED, ("hudi", "sharf"), 5),
        ("1042", 1, ORDER_COMPLETED, ("dzhinsy", "futbolka"), 4),
        ("1043", 2, ORDER_COMPLETED, ("bomber",), 4),
        ("1044", 3, ORDER_COMPLETED, ("futbolka", "krossovki"), 8),
        ("1045", 4, ORDER_COMPLETED, ("platye",), 2),
        ("1046", 5, ORDER_COMPLETED, ("sharf", "sumka"), 6),
        ("1047", 0, ORDER_READY, ("svitshot",), 1),
        ("1048", 1, ORDER_CONFIRMED, ("rubashka", "bryuki"), 2),
        ("1049", 2, ORDER_NEW, ("krossovki",), 1),
        ("1050", 3, ORDER_CANCELLED, ("botinki",), 9),
        ("1051", 4, ORDER_REJECTED, ("palto",), 11),
    )
    for index, (number, customer_index, status, slugs, days_ago) in enumerate(plans):
        phone, name = customers[customer_index]
        user = _phone(tenant.id, db, phone)
        created = _ago(days=days_ago, hours=index % 5)
        order = Order(
            tenant_id=tenant.id,
            number=number,
            user_id=user.id if user else None,
            customer_name=name,
            phone=phone,
            pickup_date=created.date(),
            pickup_time=f"{10 + index % 8}:00",
            status=status,
            total_amount=Decimal("0.00"),
            items_count=0,
            source="site",
            created_at=created,
            updated_at=created,
        )
        db.add(order)
        db.flush()
        total = Decimal("0.00")
        count = 0
        for slug in slugs:
            product = products.get(slug)
            if not product:
                continue
            final = money(product.price)
            amount = money(final * 1)
            total += amount
            count += 1
            db.add(
                OrderItem(
                    tenant_id=tenant.id,
                    order_id=order.id,
                    product_id=product.id,
                    title=product.title,
                    image_url=product.image_url,
                    unit=product.unit,
                    price=final,
                    quantity=qty(1),
                    line_total=amount,
                )
            )
        order.total_amount = money(total)
        order.items_count = count
        order.points_earned = int(total * 5) if status == ORDER_COMPLETED else 0
        history = [
            {"status": ORDER_NEW, "at": created.isoformat(), "by": "client", "comment": ""},
        ]
        if status != ORDER_NEW:
            history.append(
                {
                    "status": status,
                    "at": (created + timedelta(hours=2)).isoformat(),
                    "by": "Стилист",
                    "comment": "",
                }
            )
        order.status_history = history
    db.commit()


def _seed_loyalty(db: Session, tenant: Tenant) -> None:
    settings_row = db.scalar(
        select(LoyaltySettings).where(LoyaltySettings.tenant_id == tenant.id)
    )
    if settings_row is None:
        db.add(
            LoyaltySettings(
                tenant_id=tenant.id,
                is_active=True,
                earn_per_byn=5,
                point_value=Decimal("0.0100"),
                max_redeem_percent=30,
                min_redeem_points=100,
            )
        )
        db.commit()

    if db.scalar(select(func.count(LoyaltyAccount.id)).where(LoyaltyAccount.tenant_id == tenant.id)):
        return
    balances = (
        ("+375291113301", "Анна Ковалёва", 1480, "gold"),
        ("+375291113302", "Сергей Петров", 860, "silver"),
        ("+375291113305", "Елена Морозова", 320, "bronze"),
        ("+375291113306", "Ольга Новикова", 120, "bronze"),
    )
    for phone, name, balance, level in balances:
        account = LoyaltyAccount(
            tenant_id=tenant.id,
            user_id=(user.id if (user := _phone(tenant.id, db, phone)) else None),
            phone=phone,
            name=name,
            balance=balance,
            earned_total=balance + 200,
            spent_total=200,
            level=level,
        )
        db.add(account)
        db.flush()
        db.add(
            LoyaltyTransaction(
                tenant_id=tenant.id,
                account_id=account.id,
                kind="earn",
                points=balance,
                balance_after=balance,
                note="Начисление за полученные заказы",
                actor="Система",
                created_at=_ago(days=10),
            )
        )
        if balance >= 200:
            db.add(
                LoyaltyTransaction(
                    tenant_id=tenant.id,
                    account_id=account.id,
                    kind="spend",
                    points=-200,
                    balance_after=balance,
                    note="Списание при оформлении заказа",
                    actor="Клиент",
                    created_at=_ago(days=4),
                )
            )
    db.commit()


def _seed_carts(db: Session, tenant: Tenant, products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(Cart.id)).where(Cart.tenant_id == tenant.id)):
        return
    plans = (
        ("demo-cart-anna", "Анна Ковалёва", "+375291113301", "anna@example.by", ("platye", "sharf"), 2),
        ("demo-cart-sergey", "Сергей Петров", "+375291113302", "sergey@example.by", ("bomber", "krossovki"), 5),
        ("demo-cart-guest", "Гость", "", "", ("futbolka", "sumka"), 3),
    )
    for session_key, name, phone, email, slugs, hours in plans:
        items = []
        total = Decimal("0.00")
        for slug in slugs:
            product = products.get(slug)
            if not product:
                continue
            total += money(product.price)
            items.append(
                {
                    "product_id": product.id,
                    "slug": product.slug,
                    "title": product.title,
                    "unit": product.unit,
                    "price": float(product.price),
                    "quantity": 1.0,
                    "image_url": product.image_url or "",
                }
            )
        db.add(
            Cart(
                tenant_id=tenant.id,
                session_key=session_key,
                name=name,
                phone=phone.replace("+", "") if phone else "",
                email=email,
                items=items,
                items_count=len(items),
                total=money(total),
                status="active",
                last_activity_at=_ago(hours=hours),
                created_at=_ago(hours=hours + 1),
            )
        )
    db.commit()


def _seed_campaigns(db: Session, tenant: Tenant) -> None:
    if db.scalar(select(func.count(Campaign.id)).where(Campaign.tenant_id == tenant.id)):
        return
    customers = (
        ("Анна Ковалёва", "anna@example.by"),
        ("Сергей Петров", "sergey@example.by"),
        ("Мария Иванова", "maria@example.by"),
        ("Дмитрий Сидоров", "dmitry@example.by"),
        ("Елена Морозова", "elena@example.by"),
        ("Ольга Новикова", "olga@example.by"),
    )
    plans = (
        (
            "Новая коллекция трикотажа",
            "email",
            "Свежий трикотаж уже в павильоне",
            "Здравствуйте, {name}!\n\nВ {shop} приехала новая партия худи и свитшотов. "
            "Показываем новинки первыми — приходите на примерку или забронируйте размер на сайте.\n\n"
            "Хорошего дня!",
            "sent",
            6,
            6,
        ),
        (
            "Напоминание о брошенной корзине",
            "email",
            "В вашей корзине остались вещи",
            "Здравствуйте, {name}!\n\nВещи из вашей корзины ещё ждут в {shop}. "
            "Забронируйте их на удобное время — оплата при получении.\n\n"
            "Если передумали, просто пропустите письмо.",
            "draft",
            0,
            0,
        ),
    )
    for name, channel, subject, body, status, recipients, sent in plans:
        campaign = Campaign(
            tenant_id=tenant.id,
            name=name,
            channel=channel,
            subject=subject,
            body=body,
            segment="all",
            status=status,
            recipients_count=recipients,
            sent_count=sent,
            created_by="Стилист",
            sent_at=_ago(days=3) if status == "sent" else None,
            created_at=_ago(days=5),
        )
        db.add(campaign)
        db.flush()
        if recipients:
            for customer_name, email in customers:
                db.add(
                    CampaignRecipient(
                        tenant_id=tenant.id,
                        campaign_id=campaign.id,
                        name=customer_name,
                        contact=email,
                        status="sent" if status == "sent" else "pending",
                        sent_at=_ago(days=3) if status == "sent" else None,
                    )
                )
    db.commit()


def _seed_chats(db: Session, tenant: Tenant) -> None:
    if db.scalar(select(func.count(ChatThread.id)).where(ChatThread.tenant_id == tenant.id)):
        return
    threads = (
        (
            "demo-chat-anna",
            "Анна",
            "+375291113301",
            "open",
            (
                ("customer", "Анна", "Добрый день! Платье миди есть в размере M?", 3),
                ("staff", "Стилист", "Здравствуйте! Да, есть. Могу отложить до субботы.", 2),
                ("customer", "Анна", "Отложите, пожалуйста, приду в субботу к 12.", 1),
            ),
        ),
        (
            "demo-chat-guest",
            "Гость",
            "",
            "closed",
            (
                ("customer", "Гость", "А кроссовки белые есть на 42?", 8),
                ("staff", "Стилист", "Есть 42 и 43. Примерка в павильоне №21.", 7),
                ("customer", "Гость", "Спасибо, подойду вечером.", 7),
            ),
        ),
    )
    for key, name, phone, status, messages in threads:
        thread = ChatThread(
            tenant_id=tenant.id,
            session_key=key,
            name=name,
            phone=phone,
            email="",
            status=status,
            last_message=messages[-1][2],
            last_message_at=_ago(hours=messages[-1][3]),
            unread_staff=0,
            unread_customer=0,
        )
        db.add(thread)
        db.flush()
        for author_type, author_name, body, hours in messages:
            db.add(
                ChatMessage(
                    tenant_id=tenant.id,
                    thread_id=thread.id,
                    author_type=author_type,
                    author_name=author_name,
                    body=body,
                    created_at=_ago(hours=hours),
                )
            )
    db.commit()


def _seed_crm(db: Session, tenant: Tenant) -> None:
    if db.scalar(select(func.count(CustomerNote.id)).where(CustomerNote.tenant_id == tenant.id)):
        return
    for phone, body in DEMO_NOTES:
        db.add(
            CustomerNote(
                tenant_id=tenant.id,
                phone=phone,
                user_id=(user.id if (user := _phone(tenant.id, db, phone)) else None),
                body=body,
                author="Стилист",
                created_at=_ago(days=6),
            )
        )
    for phone, tag in DEMO_TAGS:
        db.add(CustomerTag(tenant_id=tenant.id, phone=phone, tag=tag))
    db.commit()


def _seed_upsells(db: Session, tenant: Tenant, products: dict[str, Product]) -> None:
    if db.scalar(select(func.count(UpsellRule.id)).where(UpsellRule.tenant_id == tenant.id)):
        return
    rules = (
        ("bomber", ("hudi", "futbolka")),
        ("dzhinsy", ("futbolka", "krossovki")),
        ("platye", ("sharf", "botinki")),
    )
    for slug, related in rules:
        product = products.get(slug)
        if not product:
            continue
        items = [
            {
                "product_id": products[item].id,
                "title": products[item].title,
                "price": float(products[item].price),
                "image_url": products[item].image_url,
            }
            for item in related
            if item in products
        ]
        db.add(
            UpsellRule(
                tenant_id=tenant.id,
                product_id=product.id,
                items=items,
                is_active=True,
            )
        )
    db.commit()


def _seed_tasks(db: Session, tenant: Tenant) -> None:
    if db.scalar(select(func.count(StaffTask.id)).where(StaffTask.tenant_id == tenant.id)):
        return
    owner = _phone(tenant.id, db, "+375291112288")
    if not owner:
        return
    order = db.scalar(
        select(Order)
        .where(Order.status.in_((ORDER_NEW, ORDER_CONFIRMED, ORDER_READY)))
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    today = date.today()
    tasks = (
        (
            "Подготовить витрину к выходным",
            "Переставить новую коллекцию вперёд, проверить размерные ряды и ценники.",
            TASK_TODO,
            "high",
            today + timedelta(days=2),
            None,
        ),
        (
            "Связаться с поставщиком пальто",
            "Уточнить дату поставки и наличие размеров M и L.",
            TASK_TODO,
            "high",
            today,
            None,
        ),
        (
            "Проверить остатки трикотажа",
            "Сверить фактическое наличие худи и свитшотов с учётом в админке.",
            TASK_IN_PROGRESS,
            "normal",
            today + timedelta(days=1),
            None,
        ),
        (
            "Сфотографировать новые джинсы",
            "Сделать 4 фото на светлом фоне и загрузить в карточку товара.",
            TASK_DONE,
            "normal",
            today - timedelta(days=1),
            _ago(days=1),
        ),
        (
            "Напечатать ценники на новую коллекцию",
            "Использовать шаблон 58×40, проверить старые цены и скидки.",
            TASK_TODO,
            "high",
            today - timedelta(days=1),
            None,
        ),
        (
            "Ответить на отзывы за неделю",
            "Поблагодарить за отзывы и уточнить детали по двум низким оценкам.",
            TASK_CANCELLED,
            "low",
            today - timedelta(days=3),
            None,
        ),
    )
    for title, description, status, priority, due, completed in tasks:
        db.add(
            StaffTask(
                tenant_id=tenant.id,
                title=title,
                description=description,
                status=status,
                priority=priority,
                assignee_id=owner.id,
                created_by_id=owner.id,
                order_id=order.id if order else None,
                due_date=due,
                completed_at=completed,
                created_at=_ago(days=4),
            )
        )
    db.commit()


def enrich(db: Session, tenant: Tenant) -> None:
    """Дополняет демо-магазин одежды до полного сценария."""
    categories = _upsert_categories(db, tenant)
    products = _upsert_products(db, tenant, categories)
    suppliers = _seed_suppliers(db, tenant)
    _seed_purchases(db, tenant, suppliers, products)
    _seed_stock(db, tenant, products)
    _seed_promos(db, tenant)
    _seed_reviews(db, tenant, products)
    _seed_orders(db, tenant, products)
    _seed_loyalty(db, tenant)
    _seed_carts(db, tenant, products)
    _seed_campaigns(db, tenant)
    _seed_chats(db, tenant)
    _seed_crm(db, tenant)
    _seed_upsells(db, tenant, products)
    _seed_tasks(db, tenant)
    log.info("Демо-магазин одежды наполнен: %s", tenant.slug)
