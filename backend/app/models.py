from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


ROLE_CUSTOMER = "customer"
ROLE_SELLER = "seller"
ROLE_ADMIN = "admin"
ROLES = (ROLE_CUSTOMER, ROLE_SELLER, ROLE_ADMIN)

# ─── Арендаторы (tenant) ────────────────────────────────────────────

TENANT_DRAFT = "draft"
TENANT_ONBOARDING = "onboarding"
TENANT_ACTIVE = "active"
TENANT_GRACE = "grace"
TENANT_SUSPENDED = "suspended"
TENANT_ARCHIVED = "archived"
TENANT_STATUSES = (
    TENANT_DRAFT,
    TENANT_ONBOARDING,
    TENANT_ACTIVE,
    TENANT_GRACE,
    TENANT_SUSPENDED,
    TENANT_ARCHIVED,
)

DOMAIN_SUBDOMAIN = "subdomain"
DOMAIN_CUSTOM = "custom"
DOMAIN_ALIAS = "alias"
DOMAIN_KINDS = (DOMAIN_SUBDOMAIN, DOMAIN_CUSTOM, DOMAIN_ALIAS)

MEMBERSHIP_OWNER = "owner"
MEMBERSHIP_MANAGER = "manager"
MEMBERSHIP_SELLER = "seller"
MEMBERSHIP_ACCOUNTANT = "accountant"
MEMBERSHIP_ROLES = (MEMBERSHIP_OWNER, MEMBERSHIP_MANAGER, MEMBERSHIP_SELLER, MEMBERSHIP_ACCOUNTANT)

# ─── Пользователи платформы ──────────────────────────────────────────

PLATFORM_OWNER = "owner"
PLATFORM_ADMIN = "admin"
PLATFORM_SUPPORT = "support"
PLATFORM_ACCOUNTANT = "accountant"
PLATFORM_ROLES = (PLATFORM_OWNER, PLATFORM_ADMIN, PLATFORM_SUPPORT, PLATFORM_ACCOUNTANT)

ORDER_NEW = "new"
ORDER_CONFIRMED = "confirmed"
ORDER_READY = "ready"
ORDER_COMPLETED = "completed"
ORDER_CANCELLED = "cancelled"
ORDER_REJECTED = "rejected"
ORDER_STATUSES = (ORDER_NEW, ORDER_CONFIRMED, ORDER_READY, ORDER_COMPLETED, ORDER_CANCELLED, ORDER_REJECTED)


class TenantMixin:
    """Автоматически проставляет и фильтрует tenant_id у бизнес-таблиц."""

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )


class User(TenantMixin, Base):
    """Пользователь магазина: владелец, сотрудник или покупатель."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_users_tenant_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(190), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_CUSTOMER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_personal_data: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_staff(self) -> bool:
        return self.role in (ROLE_ADMIN, ROLE_SELLER)


class PhoneVerification(Base):
    __tablename__ = "phone_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Category(TenantMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_categories_tenant_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(TenantMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_products_tenant_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(160))
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    unit: Mapped[str] = mapped_column(String(10), default="kg")  # kg | piece
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_daily_deal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stock: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    weight_note: Mapped[str] = mapped_column(String(120), default="")

    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gallery: Mapped[list] = mapped_column(JSON, default=list)
    badges: Mapped[list] = mapped_column(JSON, default=list)

    short_description: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    origin: Mapped[str] = mapped_column(String(160), default="")
    season: Mapped[str] = mapped_column(String(160), default="")
    nutrition: Mapped[dict] = mapped_column(JSON, default=dict)
    cooking_tips: Mapped[str] = mapped_column(Text, default="")
    storage_tips: Mapped[str] = mapped_column(Text, default="")

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    category: Mapped[Category | None] = relationship(back_populates="products")


class Order(TenantMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_orders_tenant_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    pickup_date: Mapped[date] = mapped_column(Date, index=True)
    pickup_time: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), default=ORDER_NEW, index=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    admin_comment: Mapped[str] = mapped_column(Text, default="")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="site")
    status_history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    user: Mapped[User | None] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(TenantMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str] = mapped_column(String(10), default="kg")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1.000"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    order: Mapped[Order] = relationship(back_populates="items")


class SiteSetting(Base):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    platform_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_users.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Tenant(Base):
    """Магазин на платформе. Все бизнес-данные привязываются к tenant."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default=TENANT_DRAFT, index=True)
    plan_code: Mapped[str] = mapped_column(String(40), default="start", index=True)
    category_preset: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="ru")
    currency: Mapped[str] = mapped_column(String(3), default="BYN")
    timezone: Mapped[str] = mapped_column(String(40), default="Europe/Minsk")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    domains: Mapped[list["TenantDomain"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", lazy="selectin"
    )
    settings: Mapped["TenantSettings | None"] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", uselist=False
    )
    memberships: Mapped[list["TenantMembership"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantDomain(Base):
    """Домен, привязанный к магазину: поддомен платформы или свой домен."""

    __tablename__ = "tenant_domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    host: Mapped[str] = mapped_column(String(253), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default=DOMAIN_SUBDOMAIN)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ssl_status: Mapped[str] = mapped_column(String(20), default="none")
    dns_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="domains")


class TenantSettings(Base):
    """Настройки магазина. Пока сосуществуют с SiteSetting(id=1)."""

    __tablename__ = "tenant_settings"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="settings")


class TenantMembership(Base):
    """Роль пользователя в конкретном магазине."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default=MEMBERSHIP_OWNER)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship()


# ─── Сервисы, тарифы и подписки ─────────────────────────────────────

class Service(Base):
    """Реестр сервисов платформы, синхронизируется из кода."""

    __tablename__ = "services"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    group: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tier: Mapped[str] = mapped_column(String(20), default="free", index=True)
    price_month: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str] = mapped_column(String(40), default="")
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price_month: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    price_year: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    quotas: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlanService(Base):
    __tablename__ = "plan_services"

    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code", ondelete="CASCADE"), primary_key=True)
    service_code: Mapped[str] = mapped_column(
        ForeignKey("services.code", ondelete="CASCADE"), primary_key=True
    )
    included: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(TenantMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="trial", index=True)
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class TenantService(TenantMixin, Base):
    __tablename__ = "tenant_services"
    __table_args__ = (UniqueConstraint("tenant_id", "service_code", name="uq_tenant_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_code: Mapped[str] = mapped_column(
        ForeignKey("services.code", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="disabled", index=True)
    source: Mapped[str] = mapped_column(String(20), default="plan")
    trial_ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    enabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    locked_by_platform: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class ServiceUsage(TenantMixin, Base):
    __tablename__ = "service_usage"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "service_code", "metric", "period_start", name="uq_service_usage_period"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_code: Mapped[str] = mapped_column(
        ForeignKey("services.code", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime] = mapped_column(UTCDateTime())
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)



class PlatformUser(Base):
    """Сотрудник платформы: доступ к центральной панели, не привязан к магазину."""

    __tablename__ = "platform_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(190), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default=PLATFORM_ADMIN, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @property
    def is_owner(self) -> bool:
        return self.role == PLATFORM_OWNER
