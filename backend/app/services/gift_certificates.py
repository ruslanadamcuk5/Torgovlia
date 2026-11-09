"""Подарочные сертификаты: выпуск, баланс, погашение и возврат."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    GIFT_ACTIVE,
    GIFT_CANCELLED,
    GIFT_EXPIRED,
    GIFT_PENDING,
    GIFT_TX_CANCEL,
    GIFT_TX_ISSUE,
    GIFT_TX_REDEEM,
    GIFT_TX_REFUND,
    GIFT_USED,
    GiftCertificate,
    GiftCertificateTransaction,
    Order,
    User,
)
from app.platform.sync import is_enabled
from app.tenancy import current_tenant
from app.utils import money


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_DAYS = 365
MAX_AMOUNT = Decimal("5000.00")
STATUS_LABELS = {
    GIFT_PENDING: "Ожидает оплаты",
    GIFT_ACTIVE: "Активен",
    GIFT_USED: "Использован",
    GIFT_EXPIRED: "Истёк",
    GIFT_CANCELLED: "Отменён",
}
OPEN_STATUSES = (GIFT_PENDING, GIFT_ACTIVE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def require_enabled(db: Session) -> int:
    tenant = current_tenant()
    if not tenant:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    if not is_enabled(db, tenant.id, "gift_certificates"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "service_disabled",
                "message": "Сервис «Подарочные сертификаты» не подключён. Включите его в разделе «Сервисы».",
            },
        )
    return tenant.id


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def _new_code(db: Session) -> str:
    for _ in range(30):
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        code = f"GIFT-{raw[:4]}-{raw[4:]}"
        exists = db.scalar(select(GiftCertificate.id).where(GiftCertificate.code == code))
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Не удалось создать код сертификата")


def expire_if_needed(cert: GiftCertificate) -> bool:
    if cert.status in OPEN_STATUSES and cert.expires_at:
        expires = cert.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < _now():
            cert.status = GIFT_EXPIRED
            cert.updated_at = _now()
            return True
    return False


def sync_expired(db: Session) -> None:
    rows = db.scalars(
        select(GiftCertificate).where(
            GiftCertificate.status.in_(OPEN_STATUSES),
            GiftCertificate.expires_at.is_not(None),
        )
    ).all()
    changed = False
    for cert in rows:
        if expire_if_needed(cert):
            changed = True
    if changed:
        db.commit()


def get_certificate(db: Session, cert_id: int) -> GiftCertificate:
    cert = db.scalar(select(GiftCertificate).where(GiftCertificate.id == cert_id))
    if not cert:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    return cert


def find_by_code(db: Session, code: str) -> GiftCertificate | None:
    return db.scalar(select(GiftCertificate).where(GiftCertificate.code == normalize_code(code)))


def _person(user: User | None) -> dict | None:
    if not user:
        return None
    return {"id": user.id, "full_name": user.full_name, "phone": user.phone}


def _transaction(tx: GiftCertificateTransaction) -> dict:
    return {
        "id": tx.id,
        "kind": tx.kind,
        "amount": float(tx.amount or 0),
        "balance_after": float(tx.balance_after or 0),
        "note": tx.note or "",
        "actor": tx.actor or "",
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def transactions(db: Session, cert_id: int) -> list[dict]:
    rows = db.scalars(
        select(GiftCertificateTransaction)
        .where(GiftCertificateTransaction.certificate_id == cert_id)
        .order_by(GiftCertificateTransaction.created_at.desc(), GiftCertificateTransaction.id.desc())
    ).all()
    return [_transaction(row) for row in rows]


def payload(cert: GiftCertificate, history: list[dict] | None = None) -> dict:
    issued_by = _person(cert.issued_by) if getattr(cert, "issued_by", None) else None
    return {
        "id": cert.id,
        "code": cert.code,
        "initial_amount": float(cert.initial_amount or 0),
        "balance": float(cert.balance or 0),
        "available": float(cert.balance or 0) if cert.status == GIFT_ACTIVE else 0.0,
        "status": cert.status,
        "status_label": STATUS_LABELS.get(cert.status, cert.status),
        "recipient_name": cert.recipient_name or "",
        "recipient_phone": cert.recipient_phone or "",
        "recipient_email": cert.recipient_email or "",
        "sender_name": cert.sender_name or "",
        "sender_phone": cert.sender_phone or "",
        "message": cert.message or "",
        "note": cert.note or "",
        "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
        "activated_at": cert.activated_at.isoformat() if cert.activated_at else None,
        "created_at": cert.created_at.isoformat() if cert.created_at else None,
        "issued_by": issued_by,
        "transactions": history or [],
    }


def _add_tx(
    db: Session,
    cert: GiftCertificate,
    kind: str,
    amount: Decimal,
    actor: str,
    note: str = "",
    order_id: int | None = None,
) -> None:
    db.add(
        GiftCertificateTransaction(
            tenant_id=cert.tenant_id,
            certificate_id=cert.id,
            order_id=order_id,
            kind=kind,
            amount=money(amount),
            balance_after=money(cert.balance),
            note=note[:200],
            actor=actor[:120],
        )
    )


def issue(
    db: Session,
    amount: float | Decimal,
    actor: str,
    *,
    recipient_name: str = "",
    recipient_phone: str = "",
    recipient_email: str = "",
    sender_name: str = "",
    sender_phone: str = "",
    message: str = "",
    note: str = "",
    user_id: int | None = None,
    issued_by_id: int | None = None,
    expires_at: datetime | None = None,
    activate: bool = True,
) -> GiftCertificate:
    value = money(Decimal(str(amount)))
    if value <= 0 or value > MAX_AMOUNT:
        raise HTTPException(
            status_code=422,
            detail=f"Сумма сертификата должна быть от 1 до {int(MAX_AMOUNT)} BYN",
        )
    now = _now()
    cert = GiftCertificate(
        code=_new_code(db),
        initial_amount=value,
        balance=value,
        status=GIFT_ACTIVE if activate else GIFT_PENDING,
        recipient_name=recipient_name.strip()[:120],
        recipient_phone=recipient_phone.strip()[:20],
        recipient_email=(recipient_email or "").strip().lower()[:190],
        sender_name=sender_name.strip()[:120],
        sender_phone=sender_phone.strip()[:20],
        message=message.strip(),
        note=note.strip(),
        user_id=user_id,
        issued_by_id=issued_by_id,
        expires_at=expires_at or now + timedelta(days=DEFAULT_DAYS),
        activated_at=now if activate else None,
    )
    db.add(cert)
    db.flush()
    if activate:
        _add_tx(db, cert, GIFT_TX_ISSUE, value, actor, "Сертификат выпущен")
    return cert


def activate(db: Session, cert: GiftCertificate, actor: str) -> GiftCertificate:
    expire_if_needed(cert)
    if cert.status == GIFT_ACTIVE:
        return cert
    if cert.status != GIFT_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Сертификат нельзя активировать: {STATUS_LABELS.get(cert.status, cert.status)}",
        )
    cert.status = GIFT_ACTIVE
    cert.activated_at = _now()
    cert.updated_at = _now()
    _add_tx(
        db,
        cert,
        GIFT_TX_ISSUE,
        Decimal(cert.initial_amount or 0),
        actor,
        "Оплата подтверждена, сертификат активирован",
    )
    return cert


def cancel(db: Session, cert: GiftCertificate, actor: str, note: str = "") -> GiftCertificate:
    if cert.status == GIFT_CANCELLED:
        return cert
    if cert.status == GIFT_USED:
        raise HTTPException(status_code=409, detail="Использованный сертификат нельзя отменить")
    cert.status = GIFT_CANCELLED
    cert.updated_at = _now()
    if note.strip():
        cert.note = f"{cert.note}\n{note.strip()}".strip()
    _add_tx(
        db,
        cert,
        GIFT_TX_CANCEL,
        Decimal("0.00"),
        actor,
        note.strip() or "Сертификат отменён",
    )
    return cert


def check(db: Session, code: str, subtotal: float | Decimal = 0) -> dict:
    cert = find_by_code(db, code)
    if not cert:
        raise HTTPException(status_code=404, detail="Сертификат с таким кодом не найден")
    expire_if_needed(cert)
    if cert.status == GIFT_PENDING:
        raise HTTPException(status_code=409, detail="Сертификат ещё не активирован")
    if cert.status == GIFT_CANCELLED:
        raise HTTPException(status_code=409, detail="Сертификат отменён")
    if cert.status == GIFT_EXPIRED:
        raise HTTPException(status_code=409, detail="Срок действия сертификата истёк")
    if cert.status != GIFT_ACTIVE:
        raise HTTPException(status_code=409, detail="Сертификат уже использован")
    balance = Decimal(cert.balance or 0)
    if balance <= 0:
        raise HTTPException(status_code=409, detail="На сертификате не осталось средств")
    wanted = money(Decimal(str(subtotal))) if subtotal else balance
    applied = min(balance, wanted)
    db.commit()
    return {
        "code": cert.code,
        "status": cert.status,
        "status_label": STATUS_LABELS.get(cert.status, cert.status),
        "balance": float(balance),
        "amount": float(applied),
        "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
        "recipient_name": cert.recipient_name or "",
    }


def redeem(
    db: Session,
    code: str,
    amount: Decimal,
    order: Order,
    actor: str = "client",
) -> Decimal:
    """Списывает сумму сертификата в счёт заказа. Возвращает фактическое списание."""
    normalized = normalize_code(code)
    if not normalized:
        return Decimal("0.00")
    cert = db.scalar(
        select(GiftCertificate)
        .where(GiftCertificate.code == normalized)
        .with_for_update()
    )
    if not cert:
        raise HTTPException(status_code=400, detail="Сертификат с таким кодом не найден")
    expire_if_needed(cert)
    if cert.status == GIFT_PENDING:
        raise HTTPException(status_code=400, detail="Сертификат ещё не активирован")
    if cert.status == GIFT_CANCELLED:
        raise HTTPException(status_code=400, detail="Сертификат отменён")
    if cert.status == GIFT_EXPIRED:
        raise HTTPException(status_code=400, detail="Срок действия сертификата истёк")
    if cert.status != GIFT_ACTIVE:
        raise HTTPException(status_code=400, detail="Сертификат уже использован")
    balance = Decimal(cert.balance or 0)
    if balance <= 0:
        raise HTTPException(status_code=400, detail="На сертификате не осталось средств")
    applied = money(min(balance, amount))
    if applied <= 0:
        return Decimal("0.00")
    cert.balance = money(balance - applied)
    if cert.balance <= 0:
        cert.status = GIFT_USED
    cert.updated_at = _now()
    _add_tx(
        db,
        cert,
        GIFT_TX_REDEEM,
        -applied,
        actor,
        f"Оплата заказа {order.number}",
        order_id=order.id,
    )
    order.gift_certificate_code = cert.code
    order.gift_certificate_amount = applied
    return applied


def restore_for_order(db: Session, order: Order, actor: str = "client") -> Decimal:
    """Возвращает остаток сертификата при отмене заказа."""
    amount = Decimal(order.gift_certificate_amount or 0)
    if amount <= 0 or not order.gift_certificate_code:
        return Decimal("0.00")
    cert = db.scalar(
        select(GiftCertificate)
        .where(GiftCertificate.code == order.gift_certificate_code)
        .with_for_update()
    )
    if not cert:
        return Decimal("0.00")
    already = db.scalar(
        select(GiftCertificateTransaction.id).where(
            GiftCertificateTransaction.certificate_id == cert.id,
            GiftCertificateTransaction.order_id == order.id,
            GiftCertificateTransaction.kind == GIFT_TX_REFUND,
        )
    )
    if already:
        return Decimal("0.00")
    cert.balance = money(Decimal(cert.balance or 0) + amount)
    if cert.status == GIFT_USED:
        cert.status = GIFT_ACTIVE
    cert.updated_at = _now()
    _add_tx(
        db,
        cert,
        GIFT_TX_REFUND,
        amount,
        actor,
        f"Возврат по заказу {order.number}",
        order_id=order.id,
    )
    return amount


def list_certificates(
    db: Session,
    status: str | None = None,
    q: str | None = None,
    limit: int = 300,
) -> list[dict]:
    sync_expired(db)
    stmt = select(GiftCertificate)
    if status and status != "all":
        stmt = stmt.where(GiftCertificate.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                GiftCertificate.code.ilike(pattern),
                GiftCertificate.recipient_name.ilike(pattern),
                GiftCertificate.recipient_phone.ilike(pattern),
                GiftCertificate.recipient_email.ilike(pattern),
                GiftCertificate.sender_name.ilike(pattern),
            )
        )
    stmt = stmt.order_by(
        GiftCertificate.status.in_((GIFT_CANCELLED, GIFT_EXPIRED, GIFT_USED)),
        GiftCertificate.created_at.desc(),
    ).limit(limit)
    rows = list(db.scalars(stmt).all())
    ids = [row.id for row in rows]
    history: dict[int, list[dict]] = {cert_id: [] for cert_id in ids}
    if ids:
        txs = db.scalars(
            select(GiftCertificateTransaction)
            .where(GiftCertificateTransaction.certificate_id.in_(ids))
            .order_by(GiftCertificateTransaction.created_at.desc())
        ).all()
        for tx in txs:
            history.setdefault(tx.certificate_id, []).append(_transaction(tx))
    return [payload(row, history.get(row.id, [])) for row in rows]


def summary(db: Session) -> dict:
    sync_expired(db)
    certs = list(db.scalars(select(GiftCertificate)).all())
    active = [cert for cert in certs if cert.status == GIFT_ACTIVE]
    soon = _now() + timedelta(days=30)
    expiring = 0
    for cert in active:
        if cert.expires_at:
            expires = cert.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= soon:
                expiring += 1
    redeemed = sum(
        float(tx.amount or 0)
        for tx in db.scalars(
            select(GiftCertificateTransaction).where(
                GiftCertificateTransaction.kind == GIFT_TX_REDEEM
            )
        ).all()
    )
    return {
        "total": len(certs),
        "active": len(active),
        "pending": sum(1 for cert in certs if cert.status == GIFT_PENDING),
        "used": sum(1 for cert in certs if cert.status == GIFT_USED),
        "expired": sum(1 for cert in certs if cert.status == GIFT_EXPIRED),
        "cancelled": sum(1 for cert in certs if cert.status == GIFT_CANCELLED),
        "outstanding": round(sum(float(cert.balance or 0) for cert in active), 2),
        "redeemed": round(abs(redeemed), 2),
        "expiring_soon": expiring,
    }
