"""API подарочных сертификатов: витрина и админка магазина."""

from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_optional_user, require_admin
from app.models import GIFT_ACTIVE, GIFT_CANCELLED, GiftCertificate, User
from app.schemas import (
    GiftCertificateCheckIn,
    GiftCertificateIssueIn,
    GiftCertificatePatchIn,
    GiftCertificateRequestIn,
)
from app.services import gift_certificates as gift_service
from app.services.audit import audit


admin_router = APIRouter(prefix="/admin/certificates", tags=["Подарочные сертификаты"])
public_router = APIRouter(prefix="/gift-certificates", tags=["Подарочные сертификаты"])


def _expires(value) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _actor(user: User) -> str:
    return user.full_name or user.phone


@admin_router.get("", summary="Сертификаты и сводка")
def certificates_list(
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(default=300, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    gift_service.require_enabled(db)
    return {
        "items": gift_service.list_certificates(db, status=status, q=q, limit=limit),
        "summary": gift_service.summary(db),
    }


@admin_router.post("", summary="Выпустить сертификат")
def certificates_issue(
    payload: GiftCertificateIssueIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = gift_service.require_enabled(db)
    cert = gift_service.issue(
        db,
        payload.amount,
        _actor(user),
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        recipient_email=str(payload.recipient_email or ""),
        sender_name=payload.sender_name,
        sender_phone=payload.sender_phone,
        message=payload.message,
        note=payload.note,
        issued_by_id=user.id,
        expires_at=_expires(payload.expires_at),
        activate=payload.activate,
    )
    audit(
        db,
        "gift.issue",
        actor=_actor(user),
        user_id=user.id,
        tenant_id=tenant_id,
        entity="gift_certificate",
        entity_id=cert.code,
        details={"amount": float(cert.initial_amount), "status": cert.status},
    )
    db.commit()
    db.refresh(cert)
    return gift_service.payload(cert, gift_service.transactions(db, cert.id))


@admin_router.patch("/{cert_id}", summary="Изменить или активировать сертификат")
def certificates_update(
    cert_id: int,
    payload: GiftCertificatePatchIn,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tenant_id = gift_service.require_enabled(db)
    cert = gift_service.get_certificate(db, cert_id)
    changes = payload.model_dump(exclude_unset=True)

    if "recipient_name" in changes and changes["recipient_name"] is not None:
        cert.recipient_name = changes["recipient_name"].strip()
    if "recipient_phone" in changes and changes["recipient_phone"] is not None:
        cert.recipient_phone = changes["recipient_phone"]
    if "recipient_email" in changes:
        cert.recipient_email = changes["recipient_email"] or ""
    if "sender_name" in changes and changes["sender_name"] is not None:
        cert.sender_name = changes["sender_name"].strip()
    if "sender_phone" in changes and changes["sender_phone"] is not None:
        cert.sender_phone = changes["sender_phone"]
    if "message" in changes and changes["message"] is not None:
        cert.message = changes["message"].strip()
    if "note" in changes and changes["note"] is not None:
        cert.note = changes["note"].strip()
    if "expires_at" in changes:
        cert.expires_at = _expires(changes["expires_at"])

    if changes.get("status") == GIFT_ACTIVE:
        gift_service.activate(db, cert, _actor(user))
    elif changes.get("status") == GIFT_CANCELLED:
        gift_service.cancel(db, cert, _actor(user), changes.get("note") or "")

    cert.updated_at = datetime.now(timezone.utc)
    audit(
        db,
        "gift.update",
        actor=_actor(user),
        user_id=user.id,
        tenant_id=tenant_id,
        entity="gift_certificate",
        entity_id=cert.code,
        details={"fields": sorted(changes.keys()), "status": cert.status},
    )
    db.commit()
    db.refresh(cert)
    return gift_service.payload(cert, gift_service.transactions(db, cert.id))


@public_router.post("/check", summary="Проверить сертификат и сумму к списанию")
def certificates_check(payload: GiftCertificateCheckIn, db: Session = Depends(get_db)):
    gift_service.require_enabled(db)
    return gift_service.check(db, payload.code, payload.subtotal or 0)


@public_router.get("/mine", summary="Мои сертификаты")
def certificates_mine(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift_service.require_enabled(db)
    gift_service.sync_expired(db)
    rows = db.scalars(
        select(GiftCertificate)
        .where(
            or_(
                GiftCertificate.user_id == user.id,
                GiftCertificate.recipient_phone == user.phone,
                GiftCertificate.sender_phone == user.phone,
            ),
            GiftCertificate.status != "cancelled",
        )
        .order_by(GiftCertificate.created_at.desc())
        .limit(50)
    ).all()
    return {
        "items": [
            {
                "id": cert.id,
                "code": cert.code,
                "balance": float(cert.balance or 0),
                "status": cert.status,
                "status_label": gift_service.STATUS_LABELS.get(cert.status, cert.status),
                "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
                "recipient_name": cert.recipient_name or "",
            }
            for cert in rows
        ]
    }


@public_router.post("/request", summary="Заявка на подарочный сертификат")
def certificates_request(
    payload: GiftCertificateRequestIn,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    tenant_id = gift_service.require_enabled(db)
    cert = gift_service.issue(
        db,
        payload.amount,
        user.full_name if user else payload.sender_name or "Покупатель",
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        recipient_email=str(payload.recipient_email or ""),
        sender_name=payload.sender_name,
        sender_phone=payload.sender_phone,
        message=payload.message,
        note="Заявка с витрины. Активировать после оплаты.",
        user_id=user.id if user else None,
        activate=False,
    )
    audit(
        db,
        "gift.request",
        actor=payload.sender_name or (user.full_name if user else "client"),
        user_id=user.id if user else None,
        tenant_id=tenant_id,
        entity="gift_certificate",
        entity_id=cert.code,
        details={"amount": float(cert.initial_amount)},
    )
    db.commit()
    db.refresh(cert)
    return {
        "code": cert.code,
        "amount": float(cert.initial_amount),
        "status": cert.status,
        "status_label": gift_service.STATUS_LABELS.get(cert.status, cert.status),
        "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
        "message": "Сертификат создан. Активируем его после подтверждения оплаты.",
    }
