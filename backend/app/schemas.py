from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.security import normalize_phone


# ─────────────────────────── Общие ───────────────────────────

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    total: int
    limit: int
    offset: int


# ─────────────────────────── Настройки сайта ───────────────────────────

class WorkingDay(BaseModel):
    weekday: int = Field(ge=0, le=6)
    label: str
    open: str = "08:00"
    close: str = "18:00"
    closed: bool = False


class Banner(BaseModel):
    id: str
    title: str = ""
    subtitle: str = ""
    image_url: str = ""
    link: str = "/catalog"
    button_text: str = "Смотреть каталог"
    is_active: bool = True


class Advantage(BaseModel):
    icon: str = "fish"
    title: str
    text: str


class Socials(BaseModel):
    tiktok: str = ""
    instagram: str = ""
    youtube: str = ""
    telegram: str = ""
    viber: str = ""
    vk: str = ""


class SiteSettings(BaseModel):
    brand_name: str = "Рыбная лавка"
    template: str = "market"
    accent_color: str = Field(default="", pattern=r"^(#[0-9a-fA-F]{6})?$")
    tagline: str = "Свежая рыба и морепродукты"
    legal_name: str = "ИП Иванов Иван Иванович"
    unp: str = "200000000"
    legal_address: str = ""
    city: str = "г. Барановичи"
    market_name: str = "рынок «Алексеевский»"
    pavilion: str = "павильон 12"
    address: str = "г. Барановичи, ул. Комсомольская, 45, рынок «Алексеевский», павильон 12"
    phone: str = "+375 29 111-22-33"
    phone_secondary: str = ""
    email: str = "info@ribnaya-lavka.by"
    working_hours: list[WorkingDay] = []
    socials: Socials = Socials()

    logo_url: str = "/assets/logo.svg"
    favicon_url: str = "/assets/favicon.svg"
    hero_image_url: str = "/assets/hero-fish.svg"
    hero_badge: str = "Рыба и морепродукты · Барановичи"
    hero_title: str = "Свежая рыба без посредников"
    hero_subtitle: str = (
        "Отборная рыба, морепродукты и деликатесы в павильоне на рынке «Алексеевский». "
        "Забронируйте онлайн — соберём заказ к вашему приходу."
    )
    hero_note: str = "Бесплатная бронь · Оплата при получении"
    about_title: str = "Рыбная лавка на Алексеевском"
    about_text: str = ""
    announcement: str = ""
    announcement_active: bool = False
    banners: list[Banner] = []
    advantages: list[Advantage] = []

    pickup_rules: str = ""
    payment_note: str = ""
    privacy_policy: str = ""
    offer_text: str = ""
    contacts_extra: str = ""

    min_order_amount: float = 10
    lead_time_minutes: int = 60
    slot_step_minutes: int = 30
    booking_days_ahead: int = 7
    slot_capacity: int = 6
    max_items: int = 30

    android_apk_url: str = ""
    android_app_version: str = "1.0.0"
    android_app_size: str = ""
    app_install_url: str = ""

    seo_title: str = "Рыбная лавка в Барановичах — рынок «Алексеевский»"
    seo_description: str = (
        "Свежая рыба, копчёности и морепродукты в Барановичах. Павильон на рынке «Алексеевский». "
        "Онлайн-бронь с самовывозом, оплата при получении."
    )
    seo_keywords: str = "рыба Барановичи, морепродукты Барановичи, рынок Алексеевский, рыбная лавка"
    seo_og_image_url: str = ""
    seo_indexing: bool = True
    analytics_yandex: str = ""
    analytics_google: str = ""
    analytics_meta_pixel: str = ""
    notify_on_new_order: bool = True
    notify_on_cancel: bool = True
    notify_telegram_chat: str = ""
    notify_sms_phone: str = ""
    notify_email: str = ""
    map_url: str = ""
    map_embed_url: str = ""

    @field_validator("working_hours")
    @classmethod
    def _default_hours(cls, value: list[WorkingDay]) -> list[WorkingDay]:
        if value:
            return value
        return [
            WorkingDay(weekday=0, label="Понедельник", open="08:00", close="18:00"),
            WorkingDay(weekday=1, label="Вторник", open="08:00", close="18:00"),
            WorkingDay(weekday=2, label="Среда", open="08:00", close="18:00"),
            WorkingDay(weekday=3, label="Четверг", open="08:00", close="18:00"),
            WorkingDay(weekday=4, label="Пятница", open="08:00", close="18:00"),
            WorkingDay(weekday=5, label="Суббота", open="08:00", close="17:00"),
            WorkingDay(weekday=6, label="Воскресенье", open="08:00", close="15:00"),
        ]


# ─────────────────────────── Пользователи и авторизация ───────────────────────────

class UserOut(ORMModel):
    id: int
    phone: str
    full_name: str
    email: str | None = None
    role: str
    is_active: bool
    is_phone_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserAdminOut(UserOut):
    orders_count: int = 0
    last_order_at: datetime | None = None
    phone_formatted: str = ""


class PhoneRequestIn(BaseModel):
    phone: str
    purpose: Literal["register", "login", "order", "reset"] = "register"

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class PhoneRequestOut(BaseModel):
    verification_id: str
    phone: str
    phone_formatted: str
    expires_in: int
    sms_sent: bool
    debug_code: str | None = None
    message: str


class PhoneConfirmIn(BaseModel):
    verification_id: str
    code: str = Field(min_length=4, max_length=8)


class PhoneConfirmOut(BaseModel):
    phone_token: str
    phone: str
    phone_formatted: str
    purpose: str
    expires_in: int


class RegisterIn(BaseModel):
    phone_token: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    consent_personal_data: bool = False

    @model_validator(mode="after")
    def _consent(self):
        if not self.consent_personal_data:
            raise ValueError("Необходимо согласие на обработку персональных данных")
        return self


class LoginIn(BaseModel):
    phone: str
    password: str
    totp_code: str | None = Field(default=None, max_length=16)

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class PhoneLoginIn(BaseModel):
    phone_token: str


class PasswordResetIn(BaseModel):
    phone_token: str
    password: str = Field(min_length=8, max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDeleteIn(BaseModel):
    password: str
    confirmation: str = Field(min_length=1, max_length=32)


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ─────────────────────────── Каталог ───────────────────────────

class CategoryOut(ORMModel):
    id: int
    slug: str
    title: str
    description: str
    image_url: str | None = None
    sort_order: int
    is_active: bool
    products_count: int = 0


class CategoryIn(BaseModel):
    slug: str | None = None
    title: str = Field(min_length=2, max_length=120)
    description: str = ""
    image_url: str | None = None
    sort_order: int = 0
    is_active: bool = True


class ProductOut(ORMModel):
    id: int
    slug: str
    title: str
    subtitle: str
    category_id: int | None = None
    category_title: str | None = None
    category_slug: str | None = None
    unit: str
    price: float
    final_price: float
    discount_percent: int
    is_daily_deal: bool
    is_available: bool
    is_active: bool
    stock: float | None = None
    weight_note: str
    image_url: str | None = None
    gallery: list[str] = []
    badges: list[str] = []
    short_description: str
    description: str = ""
    origin: str = ""
    season: str = ""
    nutrition: dict = {}
    cooking_tips: str = ""
    storage_tips: str = ""
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    can_order: bool = True
    rating: float = 0
    reviews_count: int = 0


class ProductIn(BaseModel):
    slug: str | None = None
    title: str = Field(min_length=2, max_length=160)
    subtitle: str = ""
    category_id: int | None = None
    unit: Literal["kg", "piece"] = "kg"
    price: float = Field(ge=0, le=100000)
    discount_percent: int = Field(default=0, ge=0, le=95)
    is_daily_deal: bool = False
    is_available: bool = True
    is_active: bool = True
    stock: float | None = Field(default=None, ge=0)
    weight_note: str = ""
    image_url: str | None = None
    gallery: list[str] = []
    badges: list[str] = []
    short_description: str = ""
    description: str = ""
    origin: str = ""
    season: str = ""
    nutrition: dict = {}
    cooking_tips: str = ""
    storage_tips: str = ""
    sort_order: int = 0


class ProductPatch(BaseModel):
    slug: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=160)
    subtitle: str | None = None
    category_id: int | None = None
    unit: Literal["kg", "piece"] | None = None
    price: float | None = Field(default=None, ge=0, le=100000)
    discount_percent: int | None = Field(default=None, ge=0, le=95)
    is_daily_deal: bool | None = None
    is_available: bool | None = None
    is_active: bool | None = None
    stock: float | None = None
    weight_note: str | None = None
    image_url: str | None = None
    gallery: list[str] | None = None
    badges: list[str] | None = None
    short_description: str | None = None
    description: str | None = None
    origin: str | None = None
    season: str | None = None
    nutrition: dict | None = None
    cooking_tips: str | None = None
    storage_tips: str | None = None
    sort_order: int | None = None


class SellerProductIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    unit: Literal["kg", "piece"] = "kg"
    price: float = Field(ge=0, le=100000)
    is_available: bool = True
    image_url: str | None = None
    stock: float | None = Field(default=None, ge=0)
    weight_note: str = ""
    short_description: str = ""
    category_id: int | None = None
    discount_percent: int = Field(default=0, ge=0, le=95)


class SellerProductPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    unit: Literal["kg", "piece"] | None = None
    price: float | None = Field(default=None, ge=0, le=100000)
    is_available: bool | None = None
    is_active: bool | None = None
    image_url: str | None = None
    stock: float | None = Field(default=None, ge=0)
    weight_note: str | None = None
    short_description: str | None = None
    category_id: int | None = None
    discount_percent: int | None = Field(default=None, ge=0, le=95)


# ─────────────────────────── Заказы ───────────────────────────

class OrderItemIn(BaseModel):
    product_id: int
    quantity: float = Field(gt=0, le=1000)


class OrderCreateIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=60)
    pickup_date: date
    pickup_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    phone_token: str | None = None
    comment: str = Field(default="", max_length=600)
    promo_code: str = Field(default="", max_length=32)
    fulfillment: Literal["pickup", "delivery"] = "pickup"
    delivery_zone_id: int | None = None
    delivery_address: str = Field(default="", max_length=600)
    source: Literal["site", "app"] = "site"
    consent_personal_data: bool = False

    @model_validator(mode="after")
    def _consent(self):
        if not self.consent_personal_data:
            raise ValueError("Необходимо согласие на обработку персональных данных")
        return self

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return normalize_phone(value)

    @field_validator("comment")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class OrderItemOut(ORMModel):
    id: int
    product_id: int | None
    title: str
    image_url: str | None
    unit: str
    price: float
    quantity: float
    line_total: float


class OrderOut(ORMModel):
    id: int
    number: str
    user_id: int | None
    customer_name: str
    phone: str
    phone_formatted: str = ""
    pickup_date: date
    pickup_time: str
    status: str
    comment: str
    admin_comment: str = ""
    total_amount: float
    discount_amount: float = 0
    promo_code: str = ""
    fulfillment: str = "pickup"
    delivery_zone_name: str = ""
    delivery_address: str = ""
    delivery_fee: float = 0
    items_count: int
    source: str
    status_history: list[dict] = []
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = []


class OrderStatusIn(BaseModel):
    status: Literal["new", "confirmed", "ready", "completed", "cancelled", "rejected"]
    admin_comment: str | None = None
    pickup_date: date | None = None
    pickup_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class OrderLookupIn(BaseModel):
    number: str
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class SlotOut(BaseModel):
    time: str
    available: bool
    capacity_left: int


class SlotsOut(BaseModel):
    date: date
    is_open: bool
    slots: list[SlotOut]
    message: str = ""


class PromoCodeIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$")
    kind: Literal["percent", "fixed"] = "percent"
    value: float = Field(gt=0, le=100000)
    min_order: float = Field(default=0, ge=0, le=100000)
    max_uses: int = Field(default=0, ge=0, le=100000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    note: str = Field(default="", max_length=200)

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _limits(self):
        if self.kind == "percent" and self.value > 95:
            raise ValueError("Процентная скидка не может быть больше 95%")
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("Дата окончания раньше даты начала")
        return self


class PromoCodeOut(BaseModel):
    id: int
    code: str
    kind: str
    value: float
    min_order: float
    max_uses: int
    used_count: int
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    note: str = ""
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PromoValidateIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    subtotal: float = Field(gt=0)


class PromoValidateOut(BaseModel):
    code: str
    kind: str
    value: float
    discount: float
    total: float
    note: str = ""


class DeliveryZoneIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    areas: str = Field(default="", max_length=1000)
    fee: float = Field(default=0, ge=0, le=10000)
    min_order: float = Field(default=0, ge=0, le=100000)
    free_from: float = Field(default=0, ge=0, le=100000)
    eta: str = Field(default="", max_length=60)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class DeliveryZoneOut(BaseModel):
    id: int
    name: str
    areas: str
    fee: float
    min_order: float
    free_from: float
    eta: str = ""
    is_active: bool = True
    sort_order: int = 0


class ReviewIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(default="", max_length=20)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=5, max_length=1200)
    order_number: str = Field(default="", max_length=24)
    consent_personal_data: bool = False

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value) if value.strip() else ""

    @model_validator(mode="after")
    def _consent(self):
        if not self.consent_personal_data:
            raise ValueError("Нужно согласие на обработку персональных данных")
        return self


class ReviewOut(BaseModel):
    id: int
    product_id: int
    product_title: str = ""
    product_slug: str = ""
    customer_name: str
    rating: int
    text: str
    status: str = "pending"
    admin_comment: str = ""
    is_verified_purchase: bool = False
    phone_formatted: str = ""
    published_at: datetime | None = None
    created_at: datetime | None = None


class ReviewListOut(BaseModel):
    items: list[ReviewOut]
    total: int
    average: float = 0
    distribution: dict[str, int] = {}
    enabled: bool = True


class ReviewModerationIn(BaseModel):
    status: Literal["pending", "published", "rejected"]
    admin_comment: str = Field(default="", max_length=600)


# ─────────────────────────── Админка ───────────────────────────

class RoleIn(BaseModel):
    role: Literal["customer", "seller", "admin"]


class ActiveIn(BaseModel):
    is_active: bool


class UploadOut(BaseModel):
    url: str
    filename: str
    size: int


class OnboardingStepOut(BaseModel):
    code: str
    title: str
    description: str = ""
    done: bool = False
    href: str = ""


class OnboardingOut(BaseModel):
    tenant_slug: str = ""
    steps: list[OnboardingStepOut] = []
    done: int = 0
    total: int = 0
    percent: int = 0
    complete: bool = False


class StatsOut(BaseModel):
    orders_total: int
    orders_new: int
    orders_today: int
    revenue_month: float
    revenue_today: float
    users_total: int
    customers_total: int
    products_active: int
    products_out_of_stock: int
    avg_order: float
    top_products: list[dict] = []


class QiLinkOut(BaseModel):
    kind: str
    target: str
    title: str
    url: str
    qr_url: str


class AdminUserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: Literal["customer", "seller", "admin"] | None = None
    is_active: bool | None = None


class AdminUserCreate(BaseModel):
    phone: str
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["customer", "seller", "admin"] = "seller"
    password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class SiteSettingsOut(BaseModel):
    settings: SiteSettings
    updated_at: datetime | None = None


class NotificationSettingsIn(BaseModel):
    notify_on_new_order: bool = True
    notify_on_cancel: bool = True
    notify_telegram_chat: str = Field(default="", max_length=120)
    notify_sms_phone: str = Field(default="", max_length=40)
    notify_email: str = Field(default="", max_length=200)


class NotificationTestIn(BaseModel):
    channel: Literal["telegram", "sms", "email"]
    target: str = Field(default="", max_length=200)


class StockMoveIn(BaseModel):
    kind: Literal["in", "out", "adjust"] = "in"
    quantity: float = Field(ge=0, le=1000000)
    reason: str = Field(default="", max_length=200)


# ─────────────────────────── Платформа: арендаторы ───────────────────────────

TENANT_SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"

RESERVED_SLUGS = frozenset(
    {
        "www", "api", "app", "platform", "admin", "mail", "cdn", "status",
        "docs", "support", "billing", "static", "media", "assets", "auth",
        "help", "blog", "shop", "store", "login", "register", "checkout",
    }
)


class TenantDomainOut(ORMModel):
    id: int
    host: str
    kind: str
    is_primary: bool
    verified_at: datetime | None = None
    ssl_status: str
    dns_status: str
    created_at: datetime


class TenantOut(ORMModel):
    id: int
    slug: str
    name: str
    status: str
    plan_code: str
    category_preset: str | None = None
    locale: str
    currency: str
    timezone: str
    is_demo: bool
    hosting_provider: str = ""
    hosting_tariff: str = ""
    hosting_account: str = ""
    deploy_status: str = "not_started"
    deploy_url: str = ""
    ops_note: str = ""
    created_at: datetime
    updated_at: datetime
    domains: list[TenantDomainOut] = []


class TenantCreateIn(BaseModel):
    slug: str = Field(min_length=2, max_length=63, pattern=TENANT_SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=160)
    plan_code: str = Field(default="start", max_length=40)
    category_preset: str | None = Field(default=None, max_length=40)
    locale: str = Field(default="ru", max_length=8)
    currency: str = Field(default="BYN", max_length=3)
    timezone: str = Field(default="Europe/Minsk", max_length=40)
    is_demo: bool = False
    owner_phone: str | None = None
    owner_name: str = ""
    owner_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("owner_phone")
    @classmethod
    def _owner_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_phone(value)

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str) -> str:
        value = value.strip().lower()
        if value in RESERVED_SLUGS:
            raise ValueError("Этот адрес зарезервирован платформой")
        return value


class TenantPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    status: Literal["draft", "onboarding", "active", "grace", "suspended", "archived"] | None = None
    plan_code: str | None = Field(default=None, max_length=40)
    category_preset: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, max_length=8)
    currency: str | None = Field(default=None, max_length=3)
    timezone: str | None = Field(default=None, max_length=40)


class TenantDomainIn(BaseModel):
    host: str = Field(min_length=3, max_length=253)
    kind: Literal["subdomain", "custom", "alias"] = "custom"
    is_primary: bool = False

    @field_validator("host")
    @classmethod
    def _host(cls, value: str) -> str:
        value = value.strip().lower().rstrip(".")
        if not value or " " in value or "/" in value:
            raise ValueError("Укажите домен без протокола и пути")
        return value


class PlatformStatsOut(BaseModel):
    tenants_total: int
    tenants_active: int
    tenants_trial: int
    tenants_suspended: int
    domains_total: int
    by_status: dict[str, int] = {}


# ─────────────────────────── Сервисы ───────────────────────────

class ServiceOut(BaseModel):
    code: str
    title: str
    group: str
    description: str
    tier: str
    price_month: float
    status: str
    enabled: bool
    included_in_plan: bool
    can_enable: bool
    can_disable: bool
    reason: str
    dependencies: list[str] = []
    trial_days: int = 0
    locked_by_platform: bool = False
    icon: str = ""


class ServiceListOut(BaseModel):
    plan_code: str
    items: list[ServiceOut]


class PlatformServiceUpdateIn(BaseModel):
    status: Literal["enabled", "disabled", "trial", "pending_payment", "suspended"] | None = None
    locked_by_platform: bool | None = None
    config: dict | None = None


class PlatformServiceOut(ServiceOut):
    tenant_id: int


class PlatformUserOut(ORMModel):
    id: int
    phone: str
    full_name: str
    email: str | None = None
    role: str
    is_active: bool
    totp_enabled: bool = False
    created_at: datetime
    last_login_at: datetime | None = None


class PlatformTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PlatformUserOut


# ─────────────────────────── Биллинг ───────────────────────────

class InvoiceOut(BaseModel):
    id: int
    number: str
    kind: str
    status: str
    plan_code: str | None = None
    service_code: str | None = None
    description: str
    amount: float
    currency: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    payment_method: str
    note: str
    created_at: datetime


class PlanOut(BaseModel):
    code: str
    title: str
    description: str
    price_month: float
    price_year: float
    quotas: dict = {}


class PaymentMethodOut(BaseModel):
    code: str
    title: str
    description: str
    instructions: str
    status: str
    icon: str


class BillingPageOut(BaseModel):
    plan_code: str
    plan_title: str
    price_month: float
    subscription_status: str
    period_end: datetime | None = None
    pending_plan_code: str | None = None
    open_invoices_total: float
    invoices: list[InvoiceOut] = []
    plans: list[PlanOut] = []
    payment_methods: list[PaymentMethodOut] = []


class BillingOverviewOut(BaseModel):
    plan_code: str
    plan_title: str
    price_month: float
    subscription_status: str
    period_end: datetime | None = None
    pending_plan_code: str | None = None
    open_invoices_total: float
    invoices: list[InvoiceOut] = []


class PlanChangeIn(BaseModel):
    plan_code: Literal["start", "business", "pro"]


class PlatformInvoiceCreateIn(BaseModel):
    kind: Literal["subscription", "plan_change", "addon", "manual"] = "manual"
    amount: float = Field(ge=0, le=100000)
    description: str = Field(min_length=2, max_length=300)
    plan_code: str | None = None
    service_code: str | None = None
    period_days: int = Field(default=30, ge=0, le=366)
    due_days: int = Field(default=14, ge=0, le=90)


class PlatformInvoiceOut(InvoiceOut):
    tenant_id: int


# ─────────────────────── Публичная регистрация ───────────────────────

class SignupIn(BaseModel):
    slug: str = Field(min_length=2, max_length=63, pattern=TENANT_SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=160)
    category_preset: str = Field(min_length=2, max_length=40)
    plan_code: Literal["start", "business", "pro"] | None = None
    owner_phone: str
    owner_name: str = Field(default="", max_length=120)
    owner_password: str = Field(min_length=8, max_length=128)
    offer_accepted: bool = False

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("owner_phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class CategoryPresetOut(BaseModel):
    code: str
    title: str
    description: str
    examples: list[str] = []
    icon: str = "tag"


class SignupCatalogOut(BaseModel):
    plans: list[PlanOut] = []
    categories: list[CategoryPresetOut] = []


class SignupOut(BaseModel):
    tenant_id: int
    slug: str
    name: str
    host: str
    status: str
    plan_code: str
    plan_title: str
    price_month: float
    owner_phone: str
    login_path: str = "/login"
    invoice: InvoiceOut | None = None


# ─────────────────────── Хостинг и запуск сайта ───────────────────────

class ProvisioningStepOut(BaseModel):
    code: str
    title: str
    detail: str = ""
    status: str = "pending"
    note: str = ""
    updated_at: str | None = None


class ProvisioningJobOut(BaseModel):
    id: int
    tenant_id: int
    kind: str
    status: str
    status_label: str = ""
    steps: list[ProvisioningStepOut] = []
    progress: int = 0
    steps_done: int = 0
    steps_total: int = 0
    note: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HostingOut(BaseModel):
    hosting_provider: str = ""
    hosting_tariff: str = ""
    hosting_account: str = ""
    deploy_status: str = "not_started"
    deploy_status_label: str = ""
    deploy_url: str = ""
    ops_note: str = ""
    primary_host: str = ""
    ssl_status: str = "none"
    dns_status: str = "pending"


class ProvisioningStateOut(BaseModel):
    tenant_id: int
    job: ProvisioningJobOut | None = None
    template: list[ProvisioningStepOut] = []
    hosting: HostingOut


class HostingUpdateIn(BaseModel):
    hosting_provider: str | None = Field(default=None, max_length=40)
    hosting_tariff: str | None = Field(default=None, max_length=80)
    hosting_account: str | None = Field(default=None, max_length=120)
    deploy_status: Literal[
        "not_started", "queued", "in_progress", "deployed", "failed", "paused"
    ] | None = None
    deploy_url: str | None = Field(default=None, max_length=255)
    ops_note: str | None = Field(default=None, max_length=4000)


class ProvisioningJobUpdateIn(BaseModel):
    status: Literal["queued", "in_progress", "done", "blocked", "canceled"] | None = None
    note: str | None = Field(default=None, max_length=4000)


class ProvisioningStepUpdateIn(BaseModel):
    status: Literal["pending", "in_progress", "done", "blocked", "skipped"]
    note: str | None = Field(default=None, max_length=1000)


class UptimeSummaryOut(BaseModel):
    checks: int = 0
    uptime_24h: float | None = None
    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    last_ok: bool | None = None
    last_status_code: int | None = None
    last_latency_ms: int | None = None
    last_checked_at: datetime | None = None


class UptimeCheckOut(ORMModel):
    id: int
    tenant_id: int
    url: str
    ok: bool
    status_code: int | None = None
    latency_ms: int = 0
    error: str = ""
    checked_at: datetime


class UptimeRunOut(BaseModel):
    checked: int
    ok: int
    failed: int
    results: list[UptimeCheckOut] = []


class TenantHealthOut(BaseModel):
    tenant_id: int
    slug: str
    name: str
    tenant_status: str
    deploy_status: str
    deploy_status_label: str = ""
    deploy_url: str = ""
    primary_host: str = ""
    ssl_status: str = "none"
    dns_status: str = "pending"
    open_invoices: int = 0
    job_id: int | None = None
    job_status: str | None = None
    job_progress: int = 0
    level: Literal["ok", "attention", "error"] = "ok"
    issues: list[str] = []
    uptime: UptimeSummaryOut = Field(default_factory=UptimeSummaryOut)


class OpsOverviewOut(BaseModel):
    tenants_total: int
    deployed: int
    by_status: dict[str, int] = {}
    by_level: dict[str, int] = {}
    queue_total: int = 0
    attention_total: int = 0
    queue: list[TenantHealthOut] = []
    attention: list[TenantHealthOut] = []
    items: list[TenantHealthOut] = []


# ─────────────────── Жизненный цикл и impersonation ───────────────────

class LifecycleIn(BaseModel):
    action: Literal["suspend", "resume", "archive", "restore"]
    reason: str = Field(min_length=3, max_length=500)


class LifecycleActionOut(BaseModel):
    action: str
    label: str
    enabled: bool


class LifecycleOut(BaseModel):
    tenant_id: int
    status: str
    actions: list[LifecycleActionOut] = []
    hosting: HostingOut


class ImpersonationIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    user_id: int | None = None


class ImpersonationOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: int
    tenant_slug: str
    host: str
    user: UserOut


class DashboardOut(BaseModel):
    tenants_total: int
    tenants_active: int
    tenants_onboarding: int
    tenants_suspended: int
    tenants_archived: int
    new_30d: int
    mrr: float
    mrr_plans: float
    mrr_addons: float
    arr: float
    paying_tenants: int
    paid_30d: float
    paid_month: float
    open_invoices_total: float
    open_invoices_count: int
    queue_total: int
    attention_total: int
    by_status: dict[str, int] = {}


# ─────────────────── Оповещения платформы ───────────────────

class AlertOut(BaseModel):
    tenant_id: int
    slug: str
    name: str
    severity: Literal["warning", "error"]
    message: str


class AlertsOut(BaseModel):
    generated_at: datetime
    total: int
    errors: int
    warnings: int
    telegram_configured: bool
    alerts: list[AlertOut] = []
    text: str


class AlertSendIn(BaseModel):
    test: bool = False


class AlertSendOut(BaseModel):
    sent: bool
    count: int
    message: str


# ─────────────────── Поддержка магазинов ───────────────────

class SupportTicketIn(BaseModel):
    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(default="", max_length=5000)
    priority: Literal["low", "normal", "high"] = "normal"


class SupportTicketUpdateIn(BaseModel):
    status: Literal["open", "closed"] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    body: str | None = Field(default=None, max_length=5000)


class SupportTicketOut(ORMModel):
    id: int
    tenant_id: int
    subject: str
    body: str
    priority: str
    status: str
    author: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class SupportReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    close: bool = False


class SupportTemplateOut(BaseModel):
    code: str
    title: str
    body: str


# ─────────────────── Журнал действий платформы ───────────────────

class AuditEntryOut(ORMModel):
    id: int
    tenant_id: int | None = None
    user_id: int | None = None
    platform_user_id: int | None = None
    actor: str
    action: str
    entity: str
    entity_id: str | None = None
    details: dict = {}
    created_at: datetime


class AuditListOut(BaseModel):
    items: list[AuditEntryOut]
    total: int
    limit: int
    offset: int


# ─────────────────── Инциденты и статус-страница ───────────────────

class IncidentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(default="", max_length=5000)
    severity: Literal["minor", "major", "critical"] = "minor"
    tenant_id: int | None = None


class IncidentUpdateIn(BaseModel):
    body: str = Field(min_length=2, max_length=5000)
    status: Literal["investigating", "identified", "monitoring", "resolved"] | None = None


class IncidentUpdateOut(ORMModel):
    id: int
    status: str
    body: str
    author: str
    created_at: datetime


class IncidentOut(ORMModel):
    id: int
    tenant_id: int | None = None
    tenant_name: str | None = None
    title: str
    body: str
    severity: str
    status: str
    created_by: str
    started_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    updates: list[IncidentUpdateOut] = []


class IncidentListOut(BaseModel):
    items: list[IncidentOut]
    total: int


class StatusIncidentUpdateOut(ORMModel):
    id: int
    status: str
    body: str
    created_at: datetime


class StatusIncidentOut(ORMModel):
    id: int
    title: str
    body: str
    severity: str
    status: str
    started_at: datetime
    resolved_at: datetime | None = None
    updates: list[StatusIncidentUpdateOut] = []


class StatusPageOut(BaseModel):
    updated_at: datetime
    brand_name: str = "Torgovlia"
    maintenance_notice: str = ""
    active: list[StatusIncidentOut]
    resolved: list[StatusIncidentOut]
    overall: Literal["operational", "degraded", "outage"]


# ─────────────────── Глобальные настройки платформы ───────────────────

class PlatformSettingsIn(BaseModel):
    brand_name: str | None = Field(default=None, min_length=2, max_length=80)
    support_email: EmailStr | None = None
    support_phone: str | None = Field(default=None, max_length=40)
    default_plan_code: Literal["start", "business", "pro"] | None = None
    allow_signups: bool | None = None
    max_tenants: int | None = Field(default=None, ge=0, le=100000)
    maintenance_notice: str | None = Field(default=None, max_length=500)
    payment_instructions: str | None = Field(default=None, max_length=3000)
    sms_sender: str | None = Field(default=None, max_length=40)


class PlatformSettingsOut(BaseModel):
    brand_name: str
    support_email: str
    support_phone: str
    default_plan_code: str
    allow_signups: bool
    max_tenants: int
    maintenance_notice: str
    payment_instructions: str
    sms_sender: str
    updated_at: datetime | None = None


# ─────────────────── 2FA сотрудников платформы ───────────────────

class TwoFactorStatusOut(BaseModel):
    enabled: bool
    pending: bool


class TwoFactorSetupOut(BaseModel):
    secret: str
    uri: str


class TwoFactorCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class TwoFactorEnableOut(BaseModel):
    recovery_codes: list[str]


# ─────────────────── Команда платформы ───────────────────

class PlatformTeamIn(BaseModel):
    phone: str
    full_name: str = Field(default="", max_length=120)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "support", "accountant"] = "admin"

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class PlatformTeamUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Literal["owner", "admin", "support", "accountant"] | None = None
    is_active: bool | None = None
