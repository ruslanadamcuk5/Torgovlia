"""Чек-лист запуска магазина для владельца.

Показывает, что уже готово и какой следующий шаг сделать. Проверки считаются
по фактическим данным, а не по отметкам, поэтому чек-лист нельзя «закрыть»
без результата.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Order, Product, TenantService
from app.services.settings import get_settings_model
from app.tenancy import current_tenant


def _count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def payload(db: Session) -> dict:
    tenant = current_tenant()
    settings = get_settings_model(db)

    categories = _count(db, Category)
    products = int(
        db.scalar(
            select(func.count(Product.id)).where(Product.is_active.is_(True))
        )
        or 0
    )
    services = int(
        db.scalar(
            select(func.count(TenantService.id)).where(
                TenantService.status.in_(("enabled", "trial"))
            )
        )
        or 0
    )
    orders = _count(db, Order)
    has_logo = bool(settings.logo_url and settings.logo_url != "/assets/logo.svg")
    profile_ready = bool(
        settings.brand_name.strip() and settings.phone.strip() and settings.address.strip()
    )

    steps = [
        {
            "code": "profile",
            "title": "Заполните профиль",
            "description": "Название, телефон и адрес магазина — их видят покупатели.",
            "done": profile_ready,
            "href": "/admin/settings",
        },
        {
            "code": "categories",
            "title": "Создайте категории",
            "description": "Разделы каталога помогают покупателю быстрее найти товар.",
            "done": categories >= 1,
            "href": "/admin/catalog",
        },
        {
            "code": "products",
            "title": "Добавьте минимум 3 товара",
            "description": "С фото, ценой и описанием. Демо-товары можно заменить.",
            "done": products >= 3,
            "href": "/admin/catalog",
        },
        {
            "code": "logo",
            "title": "Загрузите логотип",
            "description": "Логотип и иконка делают витрину узнаваемой.",
            "done": has_logo,
            "href": "/admin/settings",
        },
        {
            "code": "services",
            "title": "Включите нужные услуги",
            "description": "Доставка, промокоды, отзывы и другие возможности каталога.",
            "done": services >= 1,
            "href": "/admin/services",
        },
        {
            "code": "order",
            "title": "Проверьте оформление заказа",
            "description": "Сделайте тестовый заказ и убедитесь, что уведомления приходят.",
            "done": orders >= 1,
            "href": "/admin/orders",
        },
    ]
    done = sum(1 for step in steps if step["done"])
    return {
        "tenant_slug": tenant.slug if tenant else "",
        "steps": steps,
        "done": done,
        "total": len(steps),
        "percent": round(100 * done / len(steps)) if steps else 100,
        "complete": done == len(steps),
    }
