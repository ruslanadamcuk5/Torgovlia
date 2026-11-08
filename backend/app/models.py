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

DEPLOY_NOT_STARTED = "not_started"
DEPLOY_QUEUED = "queued"
DEPLOY_IN_PROGRESS = "in_progress"
DEPLOY_DEPLOYED = "deployed"
DEPLOY_FAILED = "failed"
DEPLOY_PAUSED = "paused"
DEPLOY_STATUSES = (
    DEPLOY_NOT_STARTED,
    DEPLOY_QUEUED,
    DEPLOY_IN_PROGRESS,
    DEPLOY_DEPLOYED,
    DEPLOY_FAILED,
    DEPLOY_PAUSED,
)

MEMBERSHIP_OWNER = "owner"
MEMBERSHIP_MANAGER = "manager"
MEMBERSHIP_SELLER = "seller"
MEMBERSHIP_ACCOUNTANT = "accountant"
MEMBERSHIP_ROLES = (MEMBERSHIP_OWNER, MEMBERSHIP_MANAGER, MEMBERSHIP_SELLER, MEMBERSHIP_ACCOUNTANT)

# ─── Пользователи платформы ──────────────────────────────────────────

TICKET_OPEN = "open"
TICKET_CLOSED = "closed"
TICKET_STATUSES = (TICKET_OPEN, TICKET_CLOSED)

TICKET_LOW = "low"
TICKET_NORMAL = "normal"
TICKET_HIGH = "high"
TICKET_PRIORITIES = (TICKET_LOW, TICKET_NORMAL, TICKET_HIGH)

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

PURCHASE_DRAFT = "draft"
PURCHASE_ORDERED = "ordered"
PURCHASE_RECEIVED = "received"
PURCHASE_CANCELLED = "cancelled"
PURCHASE_STATUSES = (PURCHASE_DRAFT, PURCHASE_ORDERED, PURCHASE_RECEIVED, PURCHASE_CANCELLED)

REVIEW_PENDING = "pending"
REVIEW_PUBLISHED = "published"
REVIEW_REJECTED = "rejected"
REVIEW_STATUSES = (REVIEW_PENDING, REVIEW_PUBLISHED, REVIEW_REJECTED)


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
    barcode: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
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


class StockMovement(TenantMixin, Base):
    """История движения остатков: приход, списание, заказ, отмена, инвентаризация."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_title: Mapped[str] = mapped_column(String(160), default="")
    kind: Mapped[str] = mapped_column(String(16), default="adjust", index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    stock_before: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    stock_after: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    reason: Mapped[str] = mapped_column(String(200), default="")
    actor: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Supplier(TenantMixin, Base):
    """Поставщик магазина: контакты и условия работы."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    contact_person: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(190), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    purchases: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class PurchaseOrder(TenantMixin, Base):
    """Закупка у поставщика: заявка, приёмка на склад, отмена."""

    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_purchase_orders_tenant_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), index=True)
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    supplier_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(16), default=PURCHASE_DRAFT, index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchases")
    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan", order_by="PurchaseItem.id"
    )


class PurchaseItem(TenantMixin, Base):
    """Строка закупки: товар, количество и закупочная цена."""

    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(160), default="")
    unit: Mapped[str] = mapped_column(String(10), default="piece")
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"))
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    purchase: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class PriceImport(TenantMixin, Base):
    """История импорта прайсов: файл, источник и итоги применения."""

    __tablename__ = "price_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(16), default="csv")
    total: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    actor: Mapped[str] = mapped_column(String(120), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Campaign(TenantMixin, Base):
    """Рассылка по базе клиентов: письмо или SMS."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    channel: Mapped[str] = mapped_column(String(12), default="email", index=True)
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    segment: Mapped[str] = mapped_column(String(32), default="all")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    recipients_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    demo_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignRecipient(TenantMixin, Base):
    """Снимок получателя на момент запуска рассылки."""

    __tablename__ = "campaign_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), default="")
    contact: Mapped[str] = mapped_column(String(190), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error: Mapped[str] = mapped_column(String(255), default="")
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="recipients")


class Cart(TenantMixin, Base):
    """Корзина покупателя на витрине — нужна для напоминаний о брошенной корзине."""

    __tablename__ = "carts"
    __table_args__ = (UniqueConstraint("tenant_id", "session_key", name="uq_carts_tenant_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(20), default="", index=True)
    email: Mapped[str] = mapped_column(String(190), default="")
    items: Mapped[list] = mapped_column(JSON, default=list)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    reminded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class UpsellRule(TenantMixin, Base):
    """Ручные рекомендации «с этим покупают» для карточки товара."""

    __tablename__ = "upsell_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "product_id", name="uq_upsell_tenant_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    items: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class LoyaltySettings(TenantMixin, Base):
    """Правила бонусной программы магазина."""

    __tablename__ = "loyalty_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_loyalty_settings_tenant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    earn_per_byn: Mapped[int] = mapped_column(Integer, default=5)
    point_value: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.0100"))
    max_redeem_percent: Mapped[int] = mapped_column(Integer, default=30)
    min_redeem_points: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class LoyaltyAccount(TenantMixin, Base):
    """Бонусный счёт покупателя. Гость находится по телефону."""

    __tablename__ = "loyalty_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_loyalty_tenant_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    phone: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    balance: Mapped[int] = mapped_column(Integer, default=0)
    earned_total: Mapped[int] = mapped_column(Integer, default=0)
    spent_total: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(16), default="bronze")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class LoyaltyTransaction(TenantMixin, Base):
    """История начислений, списаний и ручных корректировок баллов."""

    __tablename__ = "loyalty_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_accounts.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="earn", index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(255), default="")
    actor: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ChatThread(TenantMixin, Base):
    """Переписка с покупателем на витрине. Гость определяется ключом браузера."""

    __tablename__ = "chat_threads"
    __table_args__ = (UniqueConstraint("tenant_id", "session_key", name="uq_chat_tenant_session"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(20), default="", index=True)
    email: Mapped[str] = mapped_column(String(190), default="")
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    unread_staff: Mapped[int] = mapped_column(Integer, default=0)
    unread_customer: Mapped[int] = mapped_column(Integer, default=0)
    last_message: Mapped[str] = mapped_column(String(200), default="")
    last_message_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class ChatMessage(TenantMixin, Base):
    """Сообщение в чате: от покупателя, сотрудника или системы."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True
    )
    author_type: Mapped[str] = mapped_column(String(12), default="customer")
    author_name: Mapped[str] = mapped_column(String(120), default="")
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class CustomerNote(TenantMixin, Base):
    """Заметка менеджера в карточке клиента."""

    __tablename__ = "customer_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(String(2000))
    author: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class CustomerTag(TenantMixin, Base):
    """Метка клиента для быстрой фильтрации базы."""

    __tablename__ = "customer_tags"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", "tag", name="uq_customer_tags_phone_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    tag: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


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
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    points_used: Mapped[int] = mapped_column(Integer, default=0)
    points_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    promo_code: Mapped[str] = mapped_column(String(32), default="")
    fulfillment: Mapped[str] = mapped_column(String(12), default="pickup")
    delivery_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_zones.id", ondelete="SET NULL"), nullable=True
    )
    delivery_zone_name: Mapped[str] = mapped_column(String(80), default="")
    delivery_address: Mapped[str] = mapped_column(Text, default="")
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
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


class PromoCode(TenantMixin, Base):
    """Промокод магазина: процентная или фиксированная скидка на бронь."""

    __tablename__ = "promo_codes"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_promo_codes_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="percent")
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    min_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    max_uses: Mapped[int] = mapped_column(Integer, default=0)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class DeliveryZone(TenantMixin, Base):
    """Зона доставки: районы, стоимость и порог бесплатной доставки."""

    __tablename__ = "delivery_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    areas: Mapped[str] = mapped_column(Text, default="")
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    min_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    free_from: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    eta: Mapped[str] = mapped_column(String(60), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Review(TenantMixin, Base):
    """Отзыв покупателя о товаре с модерацией владельцем магазина."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    customer_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), default="")
    rating: Mapped[int] = mapped_column(Integer, default=5)
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default=REVIEW_PENDING, index=True)
    admin_comment: Mapped[str] = mapped_column(Text, default="")
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


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

    # Хостинг и запуск сайта (ручной/ассистируемый режим hoster.by).
    hosting_provider: Mapped[str] = mapped_column(String(40), default="")
    hosting_tariff: Mapped[str] = mapped_column(String(80), default="")
    hosting_account: Mapped[str] = mapped_column(String(120), default="")
    deploy_status: Mapped[str] = mapped_column(String(20), default=DEPLOY_NOT_STARTED, index=True)
    deploy_url: Mapped[str] = mapped_column(String(255), default="")
    ops_note: Mapped[str] = mapped_column(Text, default="")

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
    provisioning_jobs: Mapped[list["ProvisioningJob"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    support_tickets: Mapped[list["SupportTicket"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(
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
    pending_plan_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
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
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_recovery_hashes: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    @property
    def is_owner(self) -> bool:
        return self.role == PLATFORM_OWNER



class Invoice(TenantMixin, Base):
    """Счёт на оплату подписки, смены тарифа или платного сервиса."""

    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_invoices_tenant_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="subscription", index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    plan_code: Mapped[str | None] = mapped_column(
        ForeignKey("plans.code", ondelete="SET NULL"), nullable=True
    )
    service_code: Mapped[str | None] = mapped_column(
        ForeignKey("services.code", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), default="BYN")
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(40), default="")
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ProvisioningJob(TenantMixin, Base):
    """Задача запуска сайта: чек-лист хостинга, домена, SSL и публикации.

    Режим ручной/ассистируемый: платформа ведёт очередь и фиксирует шаги,
    сотрудник выполняет их в панели hoster.by и отмечает результат.
    """

    __tablename__ = "provisioning_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="launch", index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="provisioning_jobs")


class SupportTicket(TenantMixin, Base):
    """Обращение или внутренняя заметка поддержки по магазину."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default=TICKET_NORMAL, index=True)
    status: Mapped[str] = mapped_column(String(20), default=TICKET_OPEN, index=True)
    author: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="support_tickets")


class UptimeCheck(TenantMixin, Base):
    """Результат проверки доступности витрины: статус и задержка ответа."""

    __tablename__ = "uptime_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    ok: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default="")
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


# ─── Инциденты и статус-страница ─────────────────────────────────────

INCIDENT_INVESTIGATING = "investigating"
INCIDENT_IDENTIFIED = "identified"
INCIDENT_MONITORING = "monitoring"
INCIDENT_RESOLVED = "resolved"
INCIDENT_STATUSES = (
    INCIDENT_INVESTIGATING,
    INCIDENT_IDENTIFIED,
    INCIDENT_MONITORING,
    INCIDENT_RESOLVED,
)

INCIDENT_MINOR = "minor"
INCIDENT_MAJOR = "major"
INCIDENT_CRITICAL = "critical"
INCIDENT_SEVERITIES = (INCIDENT_MINOR, INCIDENT_MAJOR, INCIDENT_CRITICAL)


class Incident(Base):
    """Инцидент платформы или отдельного магазина для статус-страницы."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default=INCIDENT_MINOR, index=True)
    status: Mapped[str] = mapped_column(String(20), default=INCIDENT_INVESTIGATING, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    updates: Mapped[list["IncidentUpdate"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentUpdate.created_at",
    )
    tenant: Mapped["Tenant | None"] = relationship(back_populates="incidents")


class IncidentUpdate(Base):
    """Запись в хронологии инцидента."""

    __tablename__ = "incident_updates"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=INCIDENT_INVESTIGATING)
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    incident: Mapped["Incident"] = relationship(back_populates="updates")


class PlatformSetting(Base):
    """Глобальные настройки платформы: бренд, контакты, лимиты и режим набора."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
