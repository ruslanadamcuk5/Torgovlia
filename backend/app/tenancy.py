"""Определение арендатора по домену и контекст текущего запроса.

Пока бизнес-таблицы не получили tenant_id, модуль отвечает за:
- разбор Host и поиск магазина;
- подстановку арендатора по умолчанию в разработке;
- передачу лёгкого контекста в request.state и ContextVar.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.config import settings
from app.db import SessionLocal
from app.models import TENANT_ARCHIVED, Tenant, TenantDomain, TenantMixin


log = logging.getLogger("torgovlia.tenancy")


@dataclass(frozen=True)
class TenantContext:
    id: int
    slug: str
    name: str
    status: str
    plan_code: str
    category_preset: str | None
    business_type: str
    locale: str
    currency: str
    timezone: str

    @classmethod
    def from_model(cls, tenant: Tenant) -> "TenantContext":
        return cls(
            id=tenant.id,
            slug=tenant.slug,
            name=tenant.name,
            status=tenant.status,
            plan_code=tenant.plan_code,
            category_preset=tenant.category_preset,
            business_type=tenant.business_type or "goods",
            locale=tenant.locale,
            currency=tenant.currency,
            timezone=tenant.timezone,
        )


_current_tenant: ContextVar[TenantContext | None] = ContextVar("current_tenant", default=None)
_is_platform: ContextVar[bool] = ContextVar("is_platform", default=False)


def current_tenant() -> TenantContext | None:
    return _current_tenant.get()


def current_tenant_id() -> int | None:
    tenant = _current_tenant.get()
    return tenant.id if tenant else None


def is_platform_request() -> bool:
    return _is_platform.get()


def normalize_host(value: str | None) -> str:
    """Убирает порт, приводит к нижнему регистру и punycode."""
    host = (value or "").strip().lower()
    if not host:
        return ""
    if host.startswith("["):  # IPv6 в скобках
        host = host.split("]", 1)[0].lstrip("[")
    else:
        host = host.split(":", 1)[0]
    host = host.rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    return host


def tenant_host(slug: str) -> str:
    return f"{slug}.{settings.platform_base_domain}".lower()


def is_platform_host(host: str) -> bool:
    host = normalize_host(host)
    platform = normalize_host(settings.platform_host)
    if not host or not platform:
        return False
    return host == platform or host == f"www.{platform}"


def _default_tenant(db: Session) -> Tenant | None:
    slug = settings.default_tenant_slug
    if not slug:
        return None
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def _tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    slug = (slug or "").strip().lower()
    if not slug or "." in slug:
        return None
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant and tenant.status == TENANT_ARCHIVED:
        return None
    return tenant


def tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    """Публичный поиск магазина по slug (для демо-путей /shop/<slug>)."""
    return _tenant_by_slug(db, slug)


def _tenant_by_subdomain(db: Session, host: str) -> Tenant | None:
    base = normalize_host(settings.platform_base_domain)
    if not base or not host.endswith(f".{base}"):
        return None
    prefix = host[: -(len(base) + 1)]
    if not prefix or "." in prefix:
        return None
    return _tenant_by_slug(db, prefix)


def resolve_tenant(db: Session, host: str, header_slug: str | None = None) -> Tenant | None:
    """Ищет арендатора по точному домену, поддомену или заголовку (dev)."""
    host = normalize_host(host)

    if host:
        domain = db.scalar(select(TenantDomain).where(TenantDomain.host == host))
        if domain:
            tenant = domain.tenant
            if tenant and tenant.status != TENANT_ARCHIVED:
                return tenant

        tenant = _tenant_by_subdomain(db, host)
        if tenant:
            return tenant

    header_allowed = settings.demo_mode or not settings.is_production
    if header_slug and settings.tenant_header_enabled and header_allowed:
        tenant = _tenant_by_slug(db, header_slug)
        if tenant:
            return tenant

    # Старое поведение: локальная разработка и запросы без домена работают
    # с магазином по умолчанию.
    if not settings.is_production:
        return _default_tenant(db)
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    """Кладёт арендатора в request.state и ContextVar на время запроса."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        host = normalize_host(request.headers.get("host"))
        header_slug = request.headers.get("x-tenant-slug")
        db = SessionLocal()
        tenant: Tenant | None = None
        platform = is_platform_host(host)
        try:
            tenant = resolve_tenant(db, host, header_slug)
        except Exception:  # noqa: BLE001 — сайт не должен падать из-за тенантности
            log.exception("Не удалось определить арендатора по Host=%s", host)
        finally:
            db.close()

        context = TenantContext.from_model(tenant) if tenant else None
        token = _current_tenant.set(context)
        platform_token = _is_platform.set(platform)
        request.state.tenant = context
        request.state.is_platform = platform
        try:
            return await call_next(request)
        finally:
            _current_tenant.reset(token)
            _is_platform.reset(platform_token)


def get_tenant() -> TenantContext:
    tenant = current_tenant()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Магазин не найден. Проверьте адрес сайта.",
        )
    return tenant


# ─── Автоматическая привязка и фильтрация tenant_id ───────────────────

def tenant_get(db: Session, model, pk):  # noqa: ANN001, ANN201
    """Аналог db.get(), который не отдаёт объект чужого арендатора."""
    if not isinstance(model, type) or not issubclass(model, TenantMixin):
        return db.get(model, pk)
    if current_tenant_id() is None:
        return db.get(model, pk)
    return db.scalar(select(model).where(model.id == pk))


@event.listens_for(Session, "before_flush")
def _assign_tenant_id(session: Session, _flush_context, _instances) -> None:  # noqa: ANN001
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantMixin) and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tenant_id


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(execute_state) -> None:  # noqa: ANN001
    if not execute_state.is_select or execute_state.is_column_load:
        return
    if execute_state.execution_options.get("skip_tenant_filter"):
        return
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return
    # Один критерий на миксин вместо перебора всех mapped-классов: SQLAlchemy
    # сам раскрывает его во все подклассы TenantMixin. На горячем пути чтения
    # это убирает десятки опций с каждого SELECT.
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )
