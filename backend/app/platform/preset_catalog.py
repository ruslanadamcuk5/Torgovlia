"""Демо-ассортимент для нового магазина по категории.

Владелец получает не пустой каталог, а примеры товаров, которые можно
переименовать или удалить. Это снижает порог входа и показывает структуру.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Product
from app.utils import money


# (slug категории, название, описание, [(slug, название, цена, unit, описание)])
DEMO_CATALOG: dict[str, list[tuple[str, str, str, list[tuple[str, str, float, str, str]]]]] = {
    "fish": [
        ("morskaya-ryba", "Морская рыба", "Охлаждённая и мороженая рыба", [
            ("treska", "Треска охлаждённая", 29.90, "kg", "Филе трески для запекания и супов."),
            ("seld", "Сельдь слабосолёная", 18.90, "kg", "Классическая сельдь к картофелю."),
        ]),
        ("koprochenaya", "Копчёности", "Рыба холодного и горячего копчения", [
            ("skumbriya", "Скумбрия копчёная", 24.50, "kg", "Ароматная скумбрия горячего копчения."),
            ("forel", "Форель слабосолёная", 42.00, "kg", "Нежные ломтики для праздничного стола."),
        ]),
    ],
    "meat": [
        ("beef", "Говядина", "Вырезка, лопатка, фарш", [
            ("vyrezka", "Вырезка говяжья", 42.00, "kg", "Нежное мясо для стейков."),
            ("farsh", "Фарш домашний", 18.50, "kg", "Говядина и свинина в равных пропорциях."),
        ]),
        ("poultry", "Птица", "Курица и индейка", [
            ("grudka", "Куриная грудка", 14.50, "kg", "Филе без кожи и кости."),
            ("indeyka", "Бедро индейки", 21.00, "kg", "Сочное мясо для запекания."),
        ]),
    ],
    "flowers": [
        ("bouquets", "Букеты", "Готовые букеты на любой повод", [
            ("piony", "Букет пионов", 85.00, "piece", "Свежие пионы в крафтовой упаковке."),
            ("rozy", "Розы, 25 шт.", 120.00, "piece", "Классические розы 60 см."),
        ]),
        ("plants", "Комнатные растения", "Растения для дома и офиса", [
            ("monstera", "Монстера", 45.00, "piece", "Молодое растение высотой около 60 см."),
            ("sukkulenty", "Набор суккулентов", 32.00, "piece", "Три миниатюрных растения в горшках."),
        ]),
    ],
    "grocery": [
        ("bakaleya", "Бакалея", "Крупы, макароны, масло", [
            ("grechka", "Гречка, 1 кг", 4.90, "piece", "Крупа первого сорта."),
            ("maslo", "Масло подсолнечное, 1 л", 8.50, "piece", "Рафинированное, для жарки и салатов."),
        ]),
        ("molochnoe", "Молочное", "Молоко, сыр, творог", [
            ("moloko", "Молоко 3,2%, 1 л", 3.20, "piece", "Пастеризованное молоко."),
            ("tvorog", "Творог 5%, 500 г", 6.40, "piece", "Рассольный творог местного производства."),
        ]),
    ],
    "bakery": [
        ("bread", "Хлеб", "Свежая выпечка каждый день", [
            ("hleb", "Хлеб бородинский", 4.20, "piece", "Ржано-пшеничный хлеб на закваске."),
            ("baguette", "Багет французский", 3.80, "piece", "Хрустящая корочка, мягкий мякиш."),
        ]),
        ("sweets", "Десерты", "Торты, пирожные, печенье", [
            ("medovik", "Торт «Медовик»", 32.00, "piece", "Восемь коржей и сметанный крем."),
            ("ekler", "Пирожное «Эклер»", 4.50, "piece", "Заварное тесто и ванильный крем."),
        ]),
    ],
    "vegetables": [
        ("vegetables", "Овощи", "Сезонные овощи с грядки", [
            ("kartofel", "Картофель молодой", 2.90, "kg", "Мелкий картофель для варки."),
            ("pomidory", "Помидоры грунтовые", 6.80, "kg", "Сладкие сезонные помидоры."),
        ]),
        ("fruits", "Фрукты", "Яблоки, груши, ягоды", [
            ("yabloki", "Яблоки сезонные", 3.60, "kg", "Сочные яблоки местных сортов."),
            ("malina", "Малина, 250 г", 9.50, "piece", "Свежая малина в контейнере."),
        ]),
    ],
    "other": [
        ("hity", "Хиты", "Самые популярные товары", [
            ("tovar-1", "Пример товара", 19.90, "piece", "Замените название, цену и описание на свои."),
            ("tovar-2", "Ещё один товар", 29.90, "piece", "Добавьте фото и характеристики."),
        ]),
        ("novinki", "Новинки", "Свежие поступления", [
            ("tovar-3", "Новинка", 14.50, "piece", "Расскажите покупателям о преимуществах."),
            ("tovar-4", "Популярный набор", 49.00, "piece", "Соберите набор из нескольких товаров."),
        ]),
    ],
}

FALLBACK = DEMO_CATALOG["other"]


def seed_preset_catalog(db: Session, tenant_id: int, preset: str | None) -> int:
    rows = DEMO_CATALOG.get(preset or "") or FALLBACK
    created = 0
    for order, (slug, title, description, products) in enumerate(rows):
        if db.scalar(
            select(Category.id).where(
                Category.tenant_id == tenant_id, Category.slug == slug
            )
        ):
            continue
        category = Category(
            tenant_id=tenant_id,
            slug=slug,
            title=title,
            description=description,
            sort_order=(order + 1) * 10,
            is_active=True,
        )
        db.add(category)
        db.flush()
        for index, (product_slug, product_title, price, unit, short) in enumerate(products):
            if db.scalar(
                select(Product.id).where(
                    Product.tenant_id == tenant_id, Product.slug == product_slug
                )
            ):
                continue
            db.add(
                Product(
                    tenant_id=tenant_id,
                    slug=product_slug,
                    title=product_title,
                    subtitle="",
                    category_id=category.id,
                    unit=unit,
                    price=money(Decimal(str(price))),
                    discount_percent=0,
                    is_daily_deal=False,
                    is_available=True,
                    is_active=True,
                    stock=None,
                    weight_note="",
                    image_url=None,
                    gallery=[],
                    badges=[],
                    short_description=short,
                    description=short,
                    origin="",
                    season="",
                    nutrition={},
                    cooking_tips="",
                    storage_tips="",
                    sort_order=(index + 1) * 10,
                )
            )
            created += 1
    db.commit()
    return created
