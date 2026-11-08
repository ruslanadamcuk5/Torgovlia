"""Онлайн-чат с покупателем: переписка, непрочитанные и статусы."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatThread, User
from app.security import format_phone, normalize_phone


MAX_MESSAGES = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _customer_thread(db: Session, session_key: str) -> ChatThread | None:
    return db.scalar(select(ChatThread).where(ChatThread.session_key == session_key))


def get_or_create(
    db: Session,
    session_key: str,
    user: User | None = None,
    name: str = "",
    phone: str = "",
) -> ChatThread:
    thread = _customer_thread(db, session_key)
    if thread is None:
        thread = ChatThread(session_key=session_key, last_message_at=_now())
        db.add(thread)
        db.flush()
    if user:
        thread.user_id = thread.user_id or user.id
        thread.name = thread.name or user.full_name or ""
        thread.phone = thread.phone or user.phone or ""
        thread.email = thread.email or (user.email or "").lower()
    if name.strip():
        thread.name = name.strip()[:120]
    if phone.strip():
        try:
            thread.phone = normalize_phone(phone)
        except ValueError:
            pass
    return thread


def _add_message(
    db: Session,
    thread: ChatThread,
    author_type: str,
    body: str,
    author_name: str = "",
) -> ChatMessage:
    text = body.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Сообщение пустое")
    message = ChatMessage(
        thread_id=thread.id,
        author_type=author_type,
        author_name=author_name[:120],
        body=text[:2000],
    )
    db.add(message)
    thread.last_message = text[:200]
    thread.last_message_at = _now()
    thread.updated_at = _now()
    if author_type == "customer":
        thread.unread_staff += 1
        thread.status = "open"
    else:
        thread.unread_customer += 1
    db.flush()
    return message


def customer_send(db: Session, payload, user: User | None) -> dict:
    thread = get_or_create(db, payload.session_key, user, payload.name, payload.phone)
    if user is None and not thread.name.strip():
        raise HTTPException(status_code=422, detail="Укажите имя, чтобы магазин знал, кому отвечать")
    message = _add_message(
        db,
        thread,
        "customer",
        payload.body,
        thread.name or (user.full_name if user else "") or "Покупатель",
    )
    return {"thread": serialize_thread(thread), "message": serialize_message(message)}


def customer_thread(
    db: Session,
    session_key: str,
    after_id: int = 0,
    read: bool = True,
) -> dict:
    thread = _customer_thread(db, session_key)
    if thread is None:
        return {"thread": None, "messages": []}
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread.id, ChatMessage.id > after_id)
        .order_by(ChatMessage.id)
        .limit(MAX_MESSAGES)
    ).all()
    if read and thread.unread_customer:
        thread.unread_customer = 0
    return {
        "thread": serialize_thread(thread),
        "messages": [serialize_message(row) for row in messages],
    }


def admin_list(db: Session, status: str = "open", search: str = "", limit: int = 100) -> dict:
    stmt = select(ChatThread)
    if status in ("open", "closed"):
        stmt = stmt.where(ChatThread.status == status)
    if search.strip():
        query = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ChatThread.name.ilike(query),
                ChatThread.phone.contains(query),
                ChatThread.last_message.ilike(query),
            )
        )
    rows = db.scalars(stmt.order_by(ChatThread.last_message_at.desc()).limit(limit)).all()
    return {
        "items": [serialize_thread(row, with_preview=True) for row in rows],
        "total": len(rows),
        "summary": {
            "open": db.scalar(
                select(func.count(ChatThread.id)).where(ChatThread.status == "open")
            ) or 0,
            "unread": db.scalar(
                select(func.count(ChatThread.id)).where(ChatThread.unread_staff > 0)
            ) or 0,
        },
    }


def admin_thread(db: Session, thread_id: int, after_id: int = 0) -> dict:
    thread = db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread.id, ChatMessage.id > after_id)
        .order_by(ChatMessage.id)
        .limit(MAX_MESSAGES)
    ).all()
    if thread.unread_staff:
        thread.unread_staff = 0
    return {
        "thread": serialize_thread(thread),
        "messages": [serialize_message(row) for row in messages],
    }


def admin_reply(db: Session, thread: ChatThread, body: str, author: str) -> dict:
    message = _add_message(db, thread, "staff", body, author)
    return {"thread": serialize_thread(thread), "message": serialize_message(message)}


def set_status(db: Session, thread: ChatThread, status: str) -> ChatThread:
    thread.status = status
    thread.updated_at = _now()
    db.flush()
    return thread


def serialize_message(row: ChatMessage) -> dict:
    return {
        "id": row.id,
        "author_type": row.author_type,
        "author_name": row.author_name,
        "body": row.body,
        "created_at": row.created_at,
    }


def serialize_thread(row: ChatThread, with_preview: bool = False) -> dict:
    data = {
        "id": row.id,
        "session_key": row.session_key,
        "user_id": row.user_id,
        "name": row.name or "Гость",
        "phone": format_phone(row.phone) if row.phone else "",
        "phone_raw": row.phone,
        "email": row.email,
        "status": row.status,
        "unread_staff": row.unread_staff,
        "unread_customer": row.unread_customer,
        "last_message": row.last_message,
        "last_message_at": row.last_message_at,
        "created_at": row.created_at,
    }
    if with_preview:
        data["preview"] = row.last_message
    return data
