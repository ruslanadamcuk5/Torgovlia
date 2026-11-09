"""API задач сотрудникам для админки магазина."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import TASK_DONE, TASK_TODO, StaffTask, User, utcnow
from app.schemas import TaskIn, TaskPatchIn
from app.services import tasks as task_service
from app.services.audit import audit


router = APIRouter(prefix="/admin/tasks", tags=["Задачи сотрудников"])


@router.get("", summary="Задачи и сотрудники")
def tasks_list(
    status: str | None = None,
    assignee_id: int | None = None,
    q: str | None = None,
    limit: int = Query(default=300, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = task_service.require_enabled(db)
    items = task_service.list_tasks(
        db,
        status=status,
        assignee_id=assignee_id,
        q=q,
        limit=limit,
    )
    return {
        "items": items,
        "summary": task_service.summary(db),
        "staff": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "phone": member.phone,
                "role": member.role,
            }
            for member in task_service.staff(db)
        ],
        "orders": task_service.recent_orders(db),
        "tenant_id": tenant_id,
    }


@router.post("", summary="Создать задачу")
def tasks_create(
    payload: TaskIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = task_service.require_enabled(db)
    task_service.validate_assignee(db, payload.assignee_id)
    task_service.validate_order(db, payload.order_id)
    task = StaffTask(
        tenant_id=tenant_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        assignee_id=payload.assignee_id,
        created_by_id=user.id,
        priority=payload.priority,
        due_date=payload.due_date,
        order_id=payload.order_id,
        status=TASK_TODO,
    )
    db.add(task)
    db.flush()
    audit(
        db,
        "task.create",
        actor=user.full_name or user.phone,
        user_id=user.id,
        tenant_id=tenant_id,
        entity="task",
        entity_id=str(task.id),
        details={"title": task.title, "assignee_id": task.assignee_id},
    )
    db.commit()
    db.refresh(task)
    return task_service.detail(db, task)


@router.patch("/{task_id}", summary="Обновить задачу")
def tasks_update(
    task_id: int,
    payload: TaskPatchIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    task_service.require_enabled(db)
    task = task_service.get_task(db, task_id)
    changes = payload.model_dump(exclude_unset=True)

    if "assignee_id" in changes:
        task_service.validate_assignee(db, changes["assignee_id"])
    if "order_id" in changes:
        task_service.validate_order(db, changes["order_id"])

    if "title" in changes and changes["title"] is not None:
        task.title = changes["title"].strip()
    if "description" in changes and changes["description"] is not None:
        task.description = changes["description"].strip()
    if "priority" in changes and changes["priority"] is not None:
        task.priority = changes["priority"]
    if "assignee_id" in changes:
        task.assignee_id = changes["assignee_id"]
    if "order_id" in changes:
        task.order_id = changes["order_id"]
    if "due_date" in changes:
        task.due_date = changes["due_date"]

    if "status" in changes and changes["status"] is not None:
        task.status = changes["status"]
        if changes["status"] == TASK_DONE:
            task.completed_at = utcnow()
        else:
            task.completed_at = None

    task.updated_at = utcnow()
    audit(
        db,
        "task.update",
        actor=user.full_name or user.phone,
        user_id=user.id,
        entity="task",
        entity_id=str(task.id),
        details={"fields": sorted(changes.keys()), "status": task.status},
    )
    db.commit()
    db.refresh(task)
    return task_service.detail(db, task)
