"""API платформы: очередь запусков, хостинг и мониторинг сайтов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_platform
from app.models import PlatformUser, ProvisioningJob, Tenant
from app.platform import ops
from app.schemas import (
    HostingOut,
    HostingUpdateIn,
    OpsOverviewOut,
    ProvisioningJobOut,
    ProvisioningJobUpdateIn,
    ProvisioningStateOut,
    ProvisioningStepUpdateIn,
)
from app.services.audit import audit


router = APIRouter(prefix="/platform", tags=["Платформа: запуск и хостинг"])


def _tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.domains))
    )
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Арендатор не найден")
    return tenant


def _job_or_404(db: Session, job_id: int) -> ProvisioningJob:
    job = db.scalar(
        select(ProvisioningJob)
        .where(ProvisioningJob.id == job_id)
        .execution_options(skip_tenant_filter=True)
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return job


@router.get(
    "/ops/overview",
    response_model=OpsOverviewOut,
    summary="Мониторинг сайтов и очередь запусков",
)
def ops_overview(
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    return ops.overview(db, limit=limit)


@router.get(
    "/tenants/{tenant_id}/provisioning",
    response_model=ProvisioningStateOut,
    summary="Задача запуска и хостинг магазина",
)
def tenant_provisioning(
    tenant_id: int,
    _: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    return ops.state_payload(db, tenant)


@router.post(
    "/tenants/{tenant_id}/provisioning",
    response_model=ProvisioningStateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Поставить магазин в очередь запуска",
)
def start_provisioning(
    tenant_id: int,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    job = ops.ensure_job(db, tenant)
    audit(
        db,
        "tenant.provisioning.start",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="provisioning_job",
        entity_id=str(job.id),
        details={"status": job.status},
    )
    db.commit()
    db.refresh(tenant)
    db.refresh(job)
    return ops.state_payload(db, tenant)


@router.patch(
    "/provisioning/{job_id}",
    response_model=ProvisioningJobOut,
    summary="Изменить статус задачи запуска",
)
def update_provisioning_job(
    job_id: int,
    payload: ProvisioningJobUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    job = _job_or_404(db, job_id)
    job = ops.update_job(
        db, job, status_value=payload.status, note=payload.note
    )
    audit(
        db,
        "tenant.provisioning.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=job.tenant_id,
        entity="provisioning_job",
        entity_id=str(job.id),
        details={"status": job.status},
    )
    db.commit()
    return ops.job_payload(job)


@router.patch(
    "/provisioning/{job_id}/steps/{code}",
    response_model=ProvisioningJobOut,
    summary="Отметить шаг запуска",
)
def update_provisioning_step(
    job_id: int,
    code: str,
    payload: ProvisioningStepUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    job = _job_or_404(db, job_id)
    job = ops.update_step(
        db,
        job,
        code,
        status_value=payload.status,
        note=payload.note,
    )
    audit(
        db,
        "tenant.provisioning.step",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=job.tenant_id,
        entity="provisioning_step",
        entity_id=code,
        details={"status": payload.status},
    )
    db.commit()
    return ops.job_payload(job)


@router.patch(
    "/tenants/{tenant_id}/hosting",
    response_model=HostingOut,
    summary="Хостинг и адрес публикации",
)
def update_hosting(
    tenant_id: int,
    payload: HostingUpdateIn,
    user: PlatformUser = Depends(require_platform),
    db: Session = Depends(get_db),
):
    tenant = _tenant_or_404(db, tenant_id)
    tenant = ops.update_hosting(
        db, tenant, payload.model_dump(exclude_unset=True)
    )
    audit(
        db,
        "tenant.hosting.update",
        actor=user.full_name or user.phone,
        platform_user_id=user.id,
        tenant_id=tenant.id,
        entity="tenant",
        entity_id=str(tenant.id),
        details={"fields": sorted(payload.model_dump(exclude_unset=True))},
    )
    db.commit()
    return ops.hosting_payload(tenant)
