"""Команда платформы: роли, доступ и сброс пароля сотрудников."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_platform, require_platform_owner
from app.models import PLATFORM_OWNER, PlatformUser
from app.schemas import PlatformTeamIn, PlatformTeamUpdateIn, PlatformUserOut
from app.security import hash_password, validate_password
from app.services.audit import audit


router = APIRouter(prefix="/platform/team", tags=["Платформа: команда"])


@router.get("", response_model=list[PlatformUserOut], summary="Сотрудники платформы")
def list_team(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    return db.scalars(select(PlatformUser).order_by(PlatformUser.created_at)).all()


@router.post("", response_model=PlatformUserOut, status_code=status.HTTP_201_CREATED, summary="Добавить сотрудника")
def create_team_member(
    payload: PlatformTeamIn,
    owner: PlatformUser = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PlatformUser).where(PlatformUser.phone == payload.phone))
    if existing:
        raise HTTPException(status_code=409, detail="Сотрудник с таким номером уже есть")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = PlatformUser(
        phone=payload.phone,
        full_name=payload.full_name.strip(),
        email=str(payload.email) if payload.email else None,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        is_phone_verified=True,
    )
    db.add(user)
    db.flush()
    audit(
        db,
        "platform.team.create",
        actor=owner.full_name or owner.phone,
        platform_user_id=owner.id,
        entity="platform_user",
        entity_id=str(user.id),
        details={"phone": user.phone, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=PlatformUserOut, summary="Изменить сотрудника")
def update_team_member(
    user_id: int,
    payload: PlatformTeamUpdateIn,
    owner: PlatformUser = Depends(require_platform_owner),
    db: Session = Depends(get_db),
):
    user = db.get(PlatformUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    changes = payload.model_dump(exclude_unset=True)
    if user.id == owner.id:
        if changes.get("is_active") is False:
            raise HTTPException(status_code=409, detail="Нельзя отключить собственный доступ")
        if changes.get("role") and changes["role"] != owner.role:
            raise HTTPException(status_code=409, detail="Нельзя изменить собственную роль")

    if changes.get("role") == PLATFORM_OWNER and user.role != PLATFORM_OWNER:
        owners = db.scalar(
            select(func.count(PlatformUser.id)).where(
                PlatformUser.role == PLATFORM_OWNER, PlatformUser.is_active.is_(True)
            )
        ) or 0
        if owners and owner.role != PLATFORM_OWNER:
            raise HTTPException(status_code=403, detail="Назначать владельца может только владелец")

    if user.role == PLATFORM_OWNER and changes.get("is_active") is False:
        active_owners = db.scalar(
            select(func.count(PlatformUser.id)).where(
                PlatformUser.role == PLATFORM_OWNER, PlatformUser.is_active.is_(True)
            )
        ) or 0
        if active_owners <= 1:
            raise HTTPException(status_code=409, detail="Нельзя отключить последнего владельца платформы")

    if changes.get("password"):
        try:
            validate_password(changes["password"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        user.password_hash = hash_password(changes.pop("password"))

    for field in ("full_name", "role", "is_active"):
        if field in changes and changes[field] is not None:
            setattr(user, field, changes[field])
    if "email" in changes:
        user.email = str(changes["email"]) if changes["email"] else None

    audit(
        db,
        "platform.team.update",
        actor=owner.full_name or owner.phone,
        platform_user_id=owner.id,
        entity="platform_user",
        entity_id=str(user.id),
        details={key: str(value) for key, value in changes.items() if key != "password"},
    )
    db.commit()
    db.refresh(user)
    return user
