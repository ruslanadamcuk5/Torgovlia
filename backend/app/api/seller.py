from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_staff
from app.models import (
    ORDER_NEW,
    ORDER_READY,
    TASK_DONE,
    TASK_IN_PROGRESS,
    TASK_TODO,
    Category,
    Order,
    Product,
    StaffTask,
    User,
    utcnow,
)
from app.platform.sync import is_enabled
from app.schemas import (
    OrderOut,
    OrderStatusIn,
    ProductOut,
    SellerProductIn,
    SellerProductPatch,
    SellerTaskStatusIn,
    UploadOut,
)
from app.security import format_phone
from app.serializers import order_payload, product_admin_payload
from app.services.audit import audit
from app.services import barcode as barcode_service
from app.services import tasks as task_service
from app.services.orders import transition_order
from app.services.storage import save_image
from app.tenancy import tenant_get
from app.utils import local_today, money, slugify


router = APIRouter(prefix="/seller", tags=["Продавец"])


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


@router.get("/summary", summary="Сводка для продавца")
def summary(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    today = local_today()
    products_total = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    out_of_stock = db.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True), Product.is_available.is_(False))
    ) or 0
    new_orders = db.scalar(select(func.count(Order.id)).where(Order.status == ORDER_NEW)) or 0
    ready_orders = db.scalar(select(func.count(Order.id)).where(Order.status == ORDER_READY)) or 0
    pickups = db.scalars(
        select(Order)
        .where(Order.pickup_date == today, Order.status.in_((ORDER_NEW, "confirmed", ORDER_READY)))
        .order_by(Order.pickup_time)
        .limit(20)
    ).all()
    tasks_enabled = is_enabled(db, user.tenant_id, "tasks")
    tasks_open = 0
    if tasks_enabled:
        tasks_open = int(
            db.scalar(
                select(func.count(StaffTask.id)).where(
                    StaffTask.assignee_id == user.id,
                    StaffTask.status.in_((TASK_TODO, TASK_IN_PROGRESS)),
                )
            )
            or 0
        )
    return {
        "user": {"full_name": user.full_name, "role": user.role},
        "products_total": int(products_total),
        "out_of_stock": int(out_of_stock),
        "new_orders": int(new_orders),
        "ready_orders": int(ready_orders),
        "pickups_today": [order_payload(o) for o in pickups],
        "tasks_enabled": tasks_enabled,
        "tasks_open": tasks_open,
        "today": today.isoformat(),
    }


@router.get("/products", summary="Товары для редактирования")
def seller_products(
    q: str | None = None,
    include_inactive: bool = True,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.title.ilike(pattern), Product.slug.ilike(pattern)))
    rows = db.scalars(stmt.order_by(Product.is_active.desc(), Product.sort_order, Product.title).limit(limit)).unique().all()
    return {"items": [product_admin_payload(p) for p in rows], "total": len(rows)}


@router.post("/products", response_model=ProductOut, summary="Быстро добавить товар")
def create_product(payload: SellerProductIn, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    product = Product(
        slug=_unique_slug(db, payload.title),
        title=payload.title.strip(),
        category_id=payload.category_id,
        unit=payload.unit,
        price=money(payload.price),
        discount_percent=payload.discount_percent,
        is_available=payload.is_available,
        is_active=True,
        stock=payload.stock,
        weight_note=payload.weight_note,
        image_url=payload.image_url,
        short_description=payload.short_description,
        description=payload.short_description,
        nutrition={},
        gallery=[],
        badges=[],
        sort_order=100,
    )
    db.add(product)
    db.flush()
    if payload.barcode:
        barcode_service.assign(db, product, payload.barcode)
    else:
        barcode_service.assign_default(db, product)
    audit(db, "product.create", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"title": product.title, "price": float(product.price)})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.patch("/products/{product_id}", response_model=ProductOut, summary="Изменить товар")
def update_product(
    product_id: int,
    payload: SellerProductPatch,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    data = payload.model_dump(exclude_unset=True)
    barcode_value = data.pop("barcode", None)
    if "price" in data and data["price"] is not None:
        data["price"] = money(data["price"])
    if "title" in data and data["title"]:
        data["title"] = data["title"].strip()
        if not product.slug:
            data["slug"] = _unique_slug(db, data["title"], exclude_id=product.id)
    for key, value in data.items():
        setattr(product, key, value)
    if barcode_value:
        barcode_service.assign(db, product, barcode_value)

    audit(db, "product.update", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"fields": list(data.keys())})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.post("/products/{product_id}/availability", response_model=ProductOut, summary="Отметить наличие")
def toggle_availability(
    product_id: int,
    is_available: bool = Query(...),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    product.is_available = is_available
    audit(db, "product.availability", actor=user.phone, user_id=user.id, entity="product", entity_id=product.id,
          details={"is_available": is_available})
    db.commit()
    db.refresh(product)
    return product_admin_payload(product)


@router.post("/uploads", response_model=UploadOut, summary="Загрузить фото товара")
def upload(file: UploadFile = File(...), _: User = Depends(require_staff)):
    return save_image(file)


@router.get("/categories", summary="Категории для продавца")
def seller_categories(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.title)).all()
    return [
        {"id": c.id, "slug": c.slug, "title": c.title, "is_active": c.is_active}
        for c in rows
    ]


@router.get("/orders", summary="Заказы для сборки")
def seller_orders(
    status: str | None = None,
    pickup_date: date | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    stmt = select(Order)
    if status and status != "all":
        if status == "active":
            stmt = stmt.where(Order.status.in_((ORDER_NEW, "confirmed", ORDER_READY)))
        else:
            stmt = stmt.where(Order.status == status)
    if pickup_date:
        stmt = stmt.where(Order.pickup_date == pickup_date)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Order.number.ilike(pattern), Order.phone.ilike(pattern), Order.customer_name.ilike(pattern)))
    rows = db.scalars(stmt.order_by(Order.pickup_date.asc(), Order.pickup_time.asc(), Order.id.desc()).limit(limit)).unique().all()
    return {"items": [order_payload(o) for o in rows], "total": len(rows)}


@router.patch("/orders/{order_id}/status", response_model=OrderOut, summary="Сменить статус заказа")
def update_order_status(
    order_id: int,
    payload: OrderStatusIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    order = tenant_get(db, Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if payload.admin_comment is not None:
        order.admin_comment = payload.admin_comment.strip()
    actor = f"{user.full_name or user.phone} ({user.role})"
    order = transition_order(db, order, payload.status, actor=actor, comment=payload.admin_comment or "")
    audit(db, "order.status", actor=user.phone, user_id=user.id, entity="order", entity_id=order.id,
          details={"status": payload.status})
    db.commit()
    return order_payload(order)


@router.get("/tasks", summary="Мои задачи")
def seller_tasks(
    status: str | None = None,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    if not is_enabled(db, user.tenant_id, "tasks"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "service_disabled",
                "message": "Сервис «Задачи» не подключён.",
            },
        )
    items = task_service.list_tasks(db, status=status, mine=user.id, limit=100)
    return {
        "items": items,
        "summary": {
            "open": sum(1 for item in items if item["status"] in (TASK_TODO, TASK_IN_PROGRESS)),
            "today": sum(1 for item in items if item["due_today"]),
            "overdue": sum(1 for item in items if item["overdue"]),
        },
    }


@router.patch("/tasks/{task_id}", summary="Сменить статус своей задачи")
def seller_task_status(
    task_id: int,
    payload: SellerTaskStatusIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    if not is_enabled(db, user.tenant_id, "tasks"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "service_disabled",
                "message": "Сервис «Задачи» не подключён.",
            },
        )
    task = task_service.get_task(db, task_id)
    if task.assignee_id != user.id:
        raise HTTPException(status_code=403, detail="Задача назначена другому сотруднику")
    task.status = payload.status
    task.completed_at = utcnow() if payload.status == TASK_DONE else None
    task.updated_at = utcnow()
    audit(
        db,
        "task.status",
        actor=f"{user.full_name or user.phone} ({user.role})",
        user_id=user.id,
        entity="task",
        entity_id=str(task.id),
        details={"status": payload.status},
    )
    db.commit()
    db.refresh(task)
    return task_service.detail(db, task)
