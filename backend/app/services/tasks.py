"""Задачи сотрудникам: список, сроки, ответственные и статусы."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    ROLE_ADMIN,
    ROLE_SELLER,
    TASK_CANCELLED,
    TASK_DONE,
    TASK_IN_PROGRESS,
    TASK_TODO,
    Order,
    StaffTask,
    User,
)
from app.platform.sync import is_enabled
from app.tenancy import current_tenant
from app.utils import local_today


OPEN_STATUSES = (TASK_TODO, TASK_IN_PROGRESS)


def require_enabled(db: Session) -> int:
    """Проверяет, что сервис «Задачи» включён у текущего магазина."""
    context = current_tenant()
    if not context:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    if not is_enabled(db, context.id, "tasks"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "service_disabled",
                "message": "Сервис «Задачи» не подключён. Включите его в разделе «Сервисы».",
            },
        )
    return context.id


def staff(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role.in_((ROLE_ADMIN, ROLE_SELLER)), User.is_active.is_(True))
            .order_by(User.full_name)
        ).all()
    )


def get_task(db: Session, task_id: int) -> StaffTask:
    task = db.scalar(select(StaffTask).where(StaffTask.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


def _person(user: User | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
    }


def payload(
    task: StaffTask,
    people: dict[int, User],
    orders: dict[int, Order],
) -> dict:
    today = local_today()
    assignee = people.get(task.assignee_id) if task.assignee_id else None
    author = people.get(task.created_by_id) if task.created_by_id else None
    order = orders.get(task.order_id) if task.order_id else None
    overdue = bool(task.due_date and task.due_date < today and task.status in OPEN_STATUSES)
    due_today = bool(task.due_date == today and task.status in OPEN_STATUSES)
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "overdue": overdue,
        "due_today": due_today,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat(),
        "assignee": _person(assignee),
        "created_by": _person(author),
        "order": (
            {
                "id": order.id,
                "number": order.number,
                "customer_name": order.customer_name,
                "status": order.status,
                "total": float(order.total_amount or 0),
            }
            if order
            else None
        ),
    }


def _people(db: Session, tasks: list[StaffTask]) -> dict[int, User]:
    ids = {task.assignee_id for task in tasks if task.assignee_id}
    ids |= {task.created_by_id for task in tasks if task.created_by_id}
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {user.id: user for user in rows}


def _orders(db: Session, tasks: list[StaffTask]) -> dict[int, Order]:
    ids = {task.order_id for task in tasks if task.order_id}
    if not ids:
        return {}
    rows = db.scalars(select(Order).where(Order.id.in_(ids))).all()
    return {order.id: order for order in rows}


def detail(db: Session, task: StaffTask) -> dict:
    people = _people(db, [task])
    orders = _orders(db, [task])
    return payload(task, people, orders)


def list_tasks(
    db: Session,
    status: str | None = None,
    assignee_id: int | None = None,
    mine: int | None = None,
    q: str | None = None,
    limit: int = 300,
) -> list[dict]:
    stmt = select(StaffTask)
    if status and status != "all":
        if status == "open":
            stmt = stmt.where(StaffTask.status.in_(OPEN_STATUSES))
        else:
            stmt = stmt.where(StaffTask.status == status)
    if assignee_id is not None:
        stmt = stmt.where(StaffTask.assignee_id == assignee_id)
    if mine is not None:
        stmt = stmt.where(StaffTask.assignee_id == mine)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(StaffTask.title.ilike(pattern), StaffTask.description.ilike(pattern))
        )
    stmt = stmt.order_by(
        StaffTask.status.in_((TASK_DONE, TASK_CANCELLED)),
        StaffTask.due_date.is_(None),
        StaffTask.due_date,
        StaffTask.created_at.desc(),
    ).limit(limit)
    tasks = list(db.scalars(stmt).all())
    people = _people(db, tasks)
    orders = _orders(db, tasks)
    return [payload(task, people, orders) for task in tasks]


def summary(db: Session) -> dict:
    today = local_today()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    tasks = list(db.scalars(select(StaffTask)).all())
    open_tasks = [task for task in tasks if task.status in OPEN_STATUSES]
    done_week = [
        task
        for task in tasks
        if task.status == TASK_DONE
        and task.completed_at
        and task.completed_at.replace(tzinfo=task.completed_at.tzinfo or timezone.utc) >= week_ago
    ]
    return {
        "open": len(open_tasks),
        "todo": sum(1 for task in tasks if task.status == TASK_TODO),
        "in_progress": sum(1 for task in tasks if task.status == TASK_IN_PROGRESS),
        "overdue": sum(1 for task in open_tasks if task.due_date and task.due_date < today),
        "today": sum(1 for task in open_tasks if task.due_date == today),
        "done_week": len(done_week),
        "cancelled": sum(1 for task in tasks if task.status == TASK_CANCELLED),
        "total": len(tasks),
    }


def recent_orders(db: Session, limit: int = 80) -> list[dict]:
    rows = db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": order.id,
            "number": order.number,
            "customer_name": order.customer_name,
            "status": order.status,
            "total": float(order.total_amount or 0),
        }
        for order in rows
    ]


def validate_assignee(db: Session, assignee_id: int | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.scalar(
        select(User).where(
            User.id == assignee_id,
            User.role.in_((ROLE_ADMIN, ROLE_SELLER)),
            User.is_active.is_(True),
        )
    )
    if not user:
        raise HTTPException(status_code=422, detail="Сотрудник не найден")
    return user


def validate_order(db: Session, order_id: int | None) -> Order | None:
    if order_id is None:
        return None
    order = db.scalar(select(Order).where(Order.id == order_id))
    if not order:
        raise HTTPException(status_code=422, detail="Заказ не найден")
    return order
