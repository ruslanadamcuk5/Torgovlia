import csv
import io
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_SELLER,
    AuditLog,
    Category,
    Order,
    OrderItem,
    Product,
    User,
)
from app.schemas import (
    ActiveIn,
    AdminUserCreate,
    AdminUserUpdate,
    CategoryIn,
    OrderOut,
    OrderStatusIn,
    ProductIn,
    ProductOut,
    ProductPatch,
    RoleIn,
    SiteSettings,
    SiteSettingsOut,
    StatsOut,
    UploadOut,
    UserAdminOut,
)
from app.security import format_phone, hash_password, validate_password
from app.serializers import order_payload, product_admin_payload, product_payload
from app.services.audit import audit
from app.services.orders import transition_order
from app.services.qr import product_url, site_url
from app.services.settings import get_settings_model, save_settings, settings_updated_at
from app.services.storage import save_image
from app.utils import local_now, local_today, money, slugify


router = APIRouter(prefix="/admin", tags=["Администрирование"])


def _unique_slug(db: Session, title: str, exclude_id: int | None = None) -> str:
    base = slugify(title, fallback="tovar")
    slug = base
    index = 2
    while True:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude_id:
            stmt = stmt.where(Product.id != exclude_id)
        if not db.scalar(stmt):
            return slug
        slug = f"{base}-{index}"
        index += 1


# ─────────────────────────── Дашборд ───────────────────────────

@router.get("/stats", response_model=StatsOut, summary="Сводка по магазину")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = local_today()
    month_start = today.replace(day=1)
    active_statuses = ("confirmed", "ready", "completed")

    orders_total = db.scalar(select(func.count(Order.id))) or 0
    orders_new = db.scalar(select(func.count(Order.id)).where(Order.status == "new")) or 0
    orders_today = db.scalar(select(func.count(Order.id)).where(Order.pickup_date == today)) or 0
    revenue_today = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status == "completed", Order.pickup_date == today
        )
    ) or 0
    revenue_month = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status == "completed", Order.pickup_date >= month_start
        )
    ) or 0
    users_total = db.scalar(select(func.count(User.id))) or 0
    customers_total = db.scalar(select(func.count(User.id)).where(User.role == ROLE_CUSTOMER)) or 0
    products_active = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    out_of_stock = db.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True), Product.is_available.is_(False))
    ) or 0
    avg_order = db.scalar(
        select(func.coalesce(func.avg(Order.total_amount), 0)).where(Order.status.in_(("confirmed", "ready", "completed")))
    ) or 0

    top = db.execute(
        select(OrderItem.title, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.in_(active_statuses))
        .group_by(OrderItem.title)
        .order_by(func.sum(OrderItem.line_total).desc())
        .limit(5)
    ).all()

    return {
        "orders_total": int(orders_total),
        "orders_new": int(orders_new),
        "orders_today": int(orders_today),
        "revenue_month": float(money(revenue_month)),
        "revenue_today": float(money(revenue_today)),
        "users_total": int(users_total),
        "customers_total": int(customers_total),
        "products_active": int(products_active),
        "products_out_of_stock": int(out_of_stock),
        "avg_order": float(money(avg_order)),
        "top_products": [
            {"title": row[0], "quantity": float(row[1]), "revenue": float(money(row[2]))} for row in top
        ],
    }


# ─────────────────────────── Настройки ───────────────────────────

@router.get("/settings", response_model=SiteSettingsOut, summary="Получить настройки сайта")
def read_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"settings": get_settings_model(db), "updated_at": settings_updated_at(db)}


@router.put("/settings", response_model=SiteSettingsOut, summary="Сохранить настройки сайта")
def update_settings(
    payload: SiteSettings,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    saved = save_settings(db, payload)
    audit(db, "settings.update", actor=user.phone, user_id=user.id, entity="settings", entity_id="1")
    db.commit()
    return {"settings": saved, "updated_at": settings_updated_at(db)}


# ─────────────────────────── Каталог ───────────────────────────

@router.get("/products", summary="Все товары, включая скрытые")
def admin_products(
    q: str | None = None,
    category_id: int | None = None,
    include_inactive: bool = True,
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Product)
    count_stmt = select(func.count(Product.id))
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
        count_stmt = count_stmt.where(Product.is_active.is_(True))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(Product.title.ilike(pattern), Product.slug.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    rows = db.scalars(stmt.order_by(Product.is_active.desc(), Product.sort_order, Product.title).offset(offset).limit(limit)).unique().all()
    return {
        "items": [product_admin_payload(p) for p in rows],
        "total": int(db.scalar(count_stmt) or 0),
        "limit": limit,
        "offset": offset,
    }


@router.get("/products/{product_id}", response_model=ProductOut, summary="Товар для редактирования")
def admin_product(product_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product_admin_payload(product)


@router.post("/products", response_model=ProductOut, summary="Создать товар")
def create_product(payload: ProductIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    slug = payload.slug.strip() if payload.slug else _unique_slug(db, payload.title)
    if db.scalar(select(Product.id).where(Product.slug == slug)):
        raise HTTPException(status_code=400, detail="Такой адрес (slug) уже занят")
    product = Product(
        slug=slug,
        title=payload.title.strip(),
        subtitle=payload.subtitle,
        category_id=payload.category_id,
        unit=payload.unit,
        price=money(payload.price),
        discount_percent=payload.discount_percent,
        is_daily_deal=payload.is_daily_deal,
        is_available=payload.is_available,
        is_active=payload.is_active,
        stock=payload.stock,
        weight_note=payload.weight_note,
        image_url=payload.image_url,
        gallery=payload.gallery,
        badges=payload.badges,
        short_description=payload.short_description,
        description=payload.description,
        origin=payload.origin,
        season=payload.season,
        nutrition=payload.nutrition,
        cooking_tips=payload.cooking_tips,
        storage_tips=payload.storage_tips,
        sort_order=payload.sort_order,
    )
    db.add(product)
    db.flush()
    audit(db, "product.create", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"title": product.title})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.patch("/products/{product_id}", response_model=ProductOut, summary="Изменить товар")
def update_product(
    product_id: int,
    payload: ProductPatch,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        slug = data["slug"].strip()
        if db.scalar(select(Product.id).where(Product.slug == slug, Product.id != product_id)):
            raise HTTPException(status_code=400, detail="Такой адрес (slug) уже занят")
        data["slug"] = slug
    if "price" in data and data["price"] is not None:
        data["price"] = money(data["price"])
    for key, value in data.items():
        setattr(product, key, value)
    audit(db, "product.update", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"fields": list(data.keys())})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.delete("/products/{product_id}", summary="Снять товар с продажи")
def delete_product(
    product_id: int,
    hard: bool = False,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    used = db.scalar(select(func.count(OrderItem.id)).where(OrderItem.product_id == product_id)) or 0
    if hard and used == 0:
        db.delete(product)
        action = "product.delete"
    else:
        product.is_active = False
        product.is_available = False
        action = "product.deactivate"
    audit(db, action, actor=user.phone, user_id=user.id, entity="product", entity_id=product_id)
    db.commit()
    return {"ok": True, "message": "Товар скрыт из каталога" if not hard or used else "Товар удалён"}


# ─────────────────────────── Категории ───────────────────────────

@router.get("/categories", summary="Категории")
def admin_categories(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    counts = dict(
        db.execute(select(Product.category_id, func.count(Product.id)).group_by(Product.category_id)).all()
    )
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.title)).all()
    return {
        "items": [
            {
                "id": c.id,
                "slug": c.slug,
                "title": c.title,
                "description": c.description,
                "image_url": c.image_url,
                "sort_order": c.sort_order,
                "is_active": c.is_active,
                "products_count": int(counts.get(c.id, 0)),
            }
            for c in rows
        ]
    }


@router.post("/categories", summary="Создать категорию")
def create_category(payload: CategoryIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    slug = (payload.slug or slugify(payload.title, "category")).strip()
    if db.scalar(select(Category.id).where(Category.slug == slug)):
        raise HTTPException(status_code=400, detail="Категория с таким адресом уже существует")
    category = Category(
        slug=slug,
        title=payload.title.strip(),
        description=payload.description,
        image_url=payload.image_url,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(category)
    db.flush()
    audit(db, "category.create", actor=user.phone, user_id=user.id, entity="category", entity_id=category.id)
    db.commit()
    return {"id": category.id, "slug": category.slug, "title": category.title}


@router.patch("/categories/{category_id}", summary="Изменить категорию")
def update_category(
    category_id: int,
    payload: CategoryIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    category.title = payload.title.strip()
    category.description = payload.description
    category.image_url = payload.image_url
    category.sort_order = payload.sort_order
    category.is_active = payload.is_active
    audit(db, "category.update", actor=user.phone, user_id=user.id, entity="category", entity_id=category.id)
    db.commit()
    return {"ok": True}


@router.delete("/categories/{category_id}", summary="Удалить категорию")
def delete_category(category_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    in_use = db.scalar(select(func.count(Product.id)).where(Product.category_id == category_id)) or 0
    if in_use:
        raise HTTPException(status_code=400, detail="В категории есть товары. Сначала перенесите их.")
    db.delete(category)
    audit(db, "category.delete", actor=user.phone, user_id=user.id, entity="category", entity_id=category_id)
    db.commit()
    return {"ok": True}


# ─────────────────────────── Заказы ───────────────────────────

@router.get("/orders", summary="Брони с фильтрами")
def admin_orders(
    status: str | None = None,
    pickup_date: date | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Order)
    count_stmt = select(func.count(Order.id))
    if status and status != "all":
        if status == "active":
            stmt = stmt.where(Order.status.in_(("new", "confirmed", "ready")))
            count_stmt = count_stmt.where(Order.status.in_(("new", "confirmed", "ready")))
        else:
            stmt = stmt.where(Order.status == status)
            count_stmt = count_stmt.where(Order.status == status)
    if pickup_date:
        stmt = stmt.where(Order.pickup_date == pickup_date)
        count_stmt = count_stmt.where(Order.pickup_date == pickup_date)
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(Order.number.ilike(pattern), Order.phone.ilike(pattern), Order.customer_name.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    rows = db.scalars(stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)).unique().all()
    return {
        "items": [order_payload(o) for o in rows],
        "total": int(db.scalar(count_stmt) or 0),
        "limit": limit,
        "offset": offset,
    }


@router.get("/orders/export.csv", summary="Экспорт броней в CSV")
def export_orders(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status and status != "all":
        stmt = stmt.where(Order.status == status)
    if date_from:
        stmt = stmt.where(Order.pickup_date >= date_from)
    if date_to:
        stmt = stmt.where(Order.pickup_date <= date_to)
    rows = db.scalars(stmt).unique().all()

    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Номер", "Создан", "Клиент", "Телефон", "Дата выдачи", "Время", "Статус", "Сумма BYN", "Позиции"])
    labels = {
        "new": "Новая", "confirmed": "Подтверждена", "ready": "Готова",
        "completed": "Выдана", "cancelled": "Отменена", "rejected": "Отклонена",
    }
    for order in rows:
        writer.writerow([
            order.number,
            order.created_at.strftime("%d.%m.%Y %H:%M"),
            order.customer_name,
            format_phone(order.phone),
            order.pickup_date.strftime("%d.%m.%Y"),
            order.pickup_time,
            labels.get(order.status, order.status),
            f"{float(order.total_amount):.2f}".replace(".", ","),
            "; ".join(f"{i.title} — {float(i.quantity):g} {i.unit}" for i in order.items),
        ])
    content = buffer.getvalue().encode("utf-8")
    filename = f"orders-{local_today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/orders/{order_id}", response_model=OrderOut, summary="Детали брони")
def admin_order(order_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Бронь не найдена")
    return order_payload(order)


@router.patch("/orders/{order_id}", response_model=OrderOut, summary="Изменить бронь и статус")
def admin_update_order(
    order_id: int,
    payload: OrderStatusIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Бронь не найдена")
    if payload.admin_comment is not None:
        order.admin_comment = payload.admin_comment.strip()
    if payload.pickup_date:
        order.pickup_date = payload.pickup_date
    if payload.pickup_time:
        order.pickup_time = payload.pickup_time
    actor = f"{user.full_name or user.phone} (администратор)"
    order = transition_order(db, order, payload.status, actor=actor, comment=payload.admin_comment or "")
    audit(db, "order.update", actor=user.phone, user_id=user.id, entity="order", entity_id=order.id,
          details={"status": payload.status})
    db.commit()
    return order_payload(order)


# ─────────────────────────── Пользователи ───────────────────────────

@router.get("/users", summary="Зарегистрированные пользователи")
def admin_users(
    q: str | None = None,
    role: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    count_stmt = select(func.count(User.id))
    if q:
        pattern = f"%{q.strip()}%"
        clause = or_(User.phone.ilike(pattern), User.full_name.ilike(pattern), User.email.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if role and role != "all":
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()

    order_stats = {
        row[0]: (int(row[1]), row[2])
        for row in db.execute(
            select(Order.user_id, func.count(Order.id), func.max(Order.created_at))
            .where(Order.user_id.is_not(None))
            .group_by(Order.user_id)
        ).all()
    }
    items = []
    for user in rows:
        count, last = order_stats.get(user.id, (0, None))
        data = UserAdminOut.model_validate(user).model_dump()
        data["orders_count"] = count
        data["last_order_at"] = last
        data["phone_formatted"] = format_phone(user.phone)
        items.append(data)
    return {"items": items, "total": int(db.scalar(count_stmt) or 0)}


@router.post("/users", summary="Создать сотрудника")
def create_staff(
    payload: AdminUserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(User.phone == payload.phone)):
        raise HTTPException(status_code=400, detail="Пользователь с таким номером уже существует")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = User(
        phone=payload.phone,
        full_name=payload.full_name.strip(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_phone_verified=True,
        consent_personal_data=True,
    )
    db.add(user)
    db.flush()
    audit(db, "user.create_staff", actor=admin.phone, user_id=admin.id, entity="user", entity_id=user.id,
          details={"role": payload.role})
    db.commit()
    return {"ok": True, "id": user.id, "message": "Сотрудник создан. Пароль нужно передать лично."}


@router.patch("/users/{user_id}", summary="Изменить пользователя или роль")
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == admin.id:
        if payload.role and payload.role != ROLE_ADMIN:
            raise HTTPException(status_code=400, detail="Нельзя снять права администратора с самого себя")
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать свою учётную запись")

    if payload.role and user.role == ROLE_ADMIN and payload.role != ROLE_ADMIN:
        admins = db.scalar(select(func.count(User.id)).where(User.role == ROLE_ADMIN, User.is_active.is_(True))) or 0
        if admins <= 1:
            raise HTTPException(status_code=400, detail="В системе должен остаться хотя бы один администратор")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.email is not None:
        user.email = str(payload.email)
    if payload.role is not None:
        user.role = payload.role
        user.is_phone_verified = True
    if payload.is_active is not None:
        user.is_active = payload.is_active

    audit(db, "user.update", actor=admin.phone, user_id=admin.id, entity="user", entity_id=user.id,
          details=payload.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True, "message": "Данные пользователя обновлены"}


@router.post("/users/{user_id}/role", summary="Назначить роль")
def set_role(user_id: int, payload: RoleIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_user(user_id, AdminUserUpdate(role=payload.role), admin=admin, db=db)


@router.post("/users/{user_id}/block", summary="Заблокировать или разблокировать")
def block_user(user_id: int, payload: ActiveIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return update_user(user_id, AdminUserUpdate(is_active=payload.is_active), admin=admin, db=db)


# ─────────────────────────── QR-коды ───────────────────────────

@router.get("/qr/items", summary="Список QR-кодов сайта и товаров")
def qr_items(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    items = [
        {
            "kind": "site",
            "target": "site",
            "title": "Главная страница сайта",
            "url": site_url(),
            "qr_url": "/api/qr/site.png?size=640",
            "download_url": "/api/qr/site.png?size=1000&download=1",
        }
    ]
    products = db.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order, Product.title)
    ).all()
    for product in products:
        items.append(
            {
                "kind": "product",
                "target": product.slug,
                "title": product.title,
                "url": product_url(product.slug),
                "qr_url": f"/api/qr/product/{product.slug}.png?size=640",
                "download_url": f"/api/qr/product/{product.slug}.png?size=1000&download=1",
            }
        )
    return {"items": items, "total": len(items)}


# ─────────────────────────── Журнал и загрузки ───────────────────────────

@router.post("/uploads", response_model=UploadOut, summary="Загрузить изображение")
def upload(file: UploadFile = File(...), _: User = Depends(require_admin)):
    return save_image(file)


@router.get("/audit", summary="Журнал действий")
def audit_log(limit: int = Query(default=100, ge=1, le=500), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor": row.actor,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
