"""Реестр сервисов и тарифов платформы.

Единый источник правды. При старте синхронизируется в таблицы services/plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


TIER_FREE = "free"
TIER_START = "start"
TIER_BUSINESS = "business"
TIER_PRO = "pro"
TIER_ADDON = "addon"
TIER_PLATFORM = "platform"

PLAN_ORDER = {TIER_START: 1, TIER_BUSINESS: 2, TIER_PRO: 3}


@dataclass(frozen=True)
class ServiceDef:
    code: str
    title: str
    group: str
    description: str
    tier: str = TIER_FREE
    price_month: Decimal = Decimal("0.00")
    dependencies: tuple[str, ...] = ()
    default_enabled: bool = False
    trial_days: int = 0
    sort_order: int = 0
    icon: str = ""
    config_schema: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlanDef:
    code: str
    title: str
    description: str
    price_month: Decimal
    price_year: Decimal
    quotas: dict = field(default_factory=dict)
    sort_order: int = 0


PLANS: tuple[PlanDef, ...] = (
    PlanDef(
        code="start",
        title="Старт",
        description="Магазин, каталог, заказы и базовые шаблоны для торгового места.",
        price_month=Decimal("19.00"),
        price_year=Decimal("190.00"),
        quotas={"products": 500, "storage_gb": 1, "sms_month": 100, "users": 1, "sites": 1},
        sort_order=10,
    ),
    PlanDef(
        code="business",
        title="Бизнес",
        description="Доставка, оплата, промокоды, отзывы и сотрудники.",
        price_month=Decimal("49.00"),
        price_year=Decimal("490.00"),
        quotas={"products": 5000, "storage_gb": 5, "sms_month": 500, "users": 3, "sites": 1},
        sort_order=20,
    ),
    PlanDef(
        code="pro",
        title="Про",
        description="CRM, склад, рассылки, импорт прайсов и приоритетная поддержка.",
        price_month=Decimal("99.00"),
        price_year=Decimal("990.00"),
        quotas={"products": 0, "storage_gb": 20, "sms_month": 2000, "users": 10, "sites": 3},
        sort_order=30,
    ),
)


SERVICE_CATALOG: tuple[ServiceDef, ...] = (
    # ─── Ядро ───────────────────────────────────────────────────────
    ServiceDef("storefront", "Витрина", "Ядро", "Публичный сайт магазина", TIER_FREE,
               default_enabled=True, sort_order=10, icon="store"),
    ServiceDef("catalog", "Каталог", "Ядро", "Товары, категории, фото, цены и наличие",
               TIER_FREE, default_enabled=True, sort_order=20, icon="grid"),
    ServiceDef("orders", "Заказы", "Ядро", "Корзина, оформление, статусы и история",
               TIER_FREE, dependencies=("catalog",), default_enabled=True, sort_order=30, icon="receipt"),
    ServiceDef("customers", "Клиенты", "Ядро", "База покупателей и история покупок",
               TIER_FREE, dependencies=("orders",), default_enabled=True, sort_order=40, icon="users"),
    ServiceDef("site_settings", "Настройки сайта", "Ядро", "Контакты, режим работы, реквизиты и тексты",
               TIER_FREE, default_enabled=True, sort_order=50, icon="settings"),
    ServiceDef("templates_basic", "Базовые шаблоны", "Ядро", "Адаптивные шаблоны под категории",
               TIER_FREE, default_enabled=True, sort_order=60, icon="layout"),
    ServiceDef("sms_otp", "Подтверждение телефона", "Ядро", "Код из SMS при заказе и регистрации",
               TIER_FREE, default_enabled=True, sort_order=70, icon="message"),
    ServiceDef("pwa", "Установка на телефон", "Ядро", "PWA-иконка и офлайн-оболочка",
               TIER_FREE, dependencies=("storefront",), default_enabled=True, sort_order=80, icon="phone"),
    ServiceDef("qr_catalog", "QR-каталог", "Ядро", "QR на витрину, товар и статью",
               TIER_FREE, dependencies=("storefront",), default_enabled=True, sort_order=90, icon="qr"),
    ServiceDef("legal_pack", "Юридический пакет", "Ядро", "Политика, правила, согласия и реквизиты",
               TIER_FREE, default_enabled=True, sort_order=100, icon="shield"),
    ServiceDef("basic_reports", "Базовые отчёты", "Ядро", "Выручка, заказы и топ товаров",
               TIER_FREE, dependencies=("orders",), default_enabled=True, sort_order=110, icon="chart"),
    ServiceDef("backup_daily", "Резервные копии", "Ядро", "Ежедневный бэкап и восстановление",
               TIER_FREE, default_enabled=True, sort_order=120, icon="database"),
    ServiceDef("ssl", "SSL-сертификат", "Ядро", "Let's Encrypt с автопродлением",
               TIER_FREE, default_enabled=True, sort_order=130, icon="lock"),
    ServiceDef("subdomain", "Адрес на платформе", "Ядро", "Бесплатный поддомен магазина",
               TIER_FREE, default_enabled=True, sort_order=140, icon="globe"),
    ServiceDef("support_standard", "Поддержка", "Ядро", "Почта и база знаний",
               TIER_FREE, default_enabled=True, sort_order=150, icon="lifebuoy"),
    ServiceDef("min_order", "Минимальный заказ", "Ядро", "Порог суммы и веса",
               TIER_FREE, dependencies=("orders",), default_enabled=True, sort_order=160),
    ServiceDef("unit_conversion", "Единицы измерения", "Ядро", "Кг, штуки, упаковки и пересчёт",
               TIER_FREE, dependencies=("catalog",), default_enabled=True, sort_order=170),
    ServiceDef("promo_banners", "Акционные баннеры", "Ядро", "Баннеры, таймеры и подборки",
               TIER_FREE, dependencies=("storefront",), default_enabled=True, sort_order=180),
    ServiceDef("blog", "Статьи и блог", "Ядро", "Полезный контент и советы",
               TIER_FREE, dependencies=("storefront",), default_enabled=True, sort_order=190),

    # ─── Продажи ────────────────────────────────────────────────────
    ServiceDef("staff_roles", "Сотрудники и роли", "Продажи", "Приглашения и права сотрудников",
               TIER_BUSINESS, sort_order=210, icon="users"),
    ServiceDef("online_payments", "Онлайн-оплата", "Продажи", "Карты и ЕРИП через эквайринг арендатора",
               TIER_BUSINESS, dependencies=("orders",), sort_order=220, icon="card"),
    ServiceDef("delivery", "Доставка", "Продажи", "Зоны, стоимость, интервалы и курьеры",
               TIER_BUSINESS, dependencies=("orders",), sort_order=230, icon="truck"),
    ServiceDef("pickup_slots", "Интервалы самовывоза", "Продажи", "Слоты, лимиты и напоминания",
               TIER_BUSINESS, dependencies=("orders",), sort_order=240, icon="clock"),
    ServiceDef("preorder", "Предзаказ", "Продажи", "Заказ товара под заказ",
               TIER_BUSINESS, dependencies=("orders",), sort_order=250),
    ServiceDef("promo_codes", "Промокоды", "Продажи", "Скидки, лимиты и персональные коды",
               TIER_BUSINESS, dependencies=("orders",), sort_order=260, icon="tag"),
    ServiceDef("reviews", "Отзывы и рейтинги", "Продажи", "Отзывы с модерацией",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=270, icon="star"),
    ServiceDef("price_tags", "Ценники и этикетки", "Продажи", "Печать ценников и составных этикеток",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=280, icon="printer"),
    ServiceDef("order_tracking", "Статус заказа", "Продажи", "Страница отслеживания и уведомления",
               TIER_BUSINESS, dependencies=("orders",), sort_order=290),
    ServiceDef("seo_tools", "SEO-инструменты", "Продажи", "Meta, sitemap, robots и микроразметка",
               TIER_BUSINESS, dependencies=("storefront",), sort_order=300, icon="search"),
    ServiceDef("pixels_analytics", "Пиксели и аналитика", "Продажи", "Google, Meta, Яндекс и цели",
               TIER_BUSINESS, dependencies=("storefront",), sort_order=310, icon="chart"),
    ServiceDef("barcode", "Штрихкоды", "Продажи", "Сканирование и поиск по коду",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=320),
    ServiceDef("labels", "Печать этикеток", "Продажи", "Состав, срок годности и весы",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=330),
    ServiceDef("certificates", "Сертификаты качества", "Продажи", "Документы к товару",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=340),
    ServiceDef("tasks", "Задачи", "Продажи", "Поручения сотрудникам и напоминания",
               TIER_BUSINESS, dependencies=("staff_roles",), sort_order=350),
    ServiceDef("support_chat", "Чат с покупателем", "Продажи", "Онлайн-чат на витрине",
               TIER_BUSINESS, dependencies=("storefront",), sort_order=360),
    ServiceDef("wholesale", "Оптовые цены", "Продажи", "Вторая цена для оптовиков",
               TIER_BUSINESS, dependencies=("catalog",), sort_order=370),

    # ─── Маркетинг ──────────────────────────────────────────────────
    ServiceDef("loyalty", "Бонусная программа", "Маркетинг", "Баллы, уровни и списание",
               TIER_PRO, dependencies=("customers",), sort_order=410, icon="gift"),
    ServiceDef("email_marketing", "Email-рассылки", "Маркетинг", "Письма, шаблоны и сегменты",
               TIER_PRO, dependencies=("customers",), sort_order=420, icon="mail"),
    ServiceDef("push_notifications", "Push-уведомления", "Маркетинг", "Web-push о заказах и акциях",
               TIER_PRO, dependencies=("pwa",), sort_order=430),
    ServiceDef("landing_builder", "Конструктор страниц", "Маркетинг", "Блоки главной и акций",
               TIER_PRO, dependencies=("storefront",), sort_order=440),
    ServiceDef("dynamic_pricing", "Динамические цены", "Маркетинг", "Правила скидок по времени и остаткам",
               TIER_PRO, dependencies=("catalog",), sort_order=450),
    ServiceDef("price_import", "Импорт прайсов", "Маркетинг", "Excel, CSV и почта с распознаванием",
               TIER_PRO, dependencies=("catalog",), trial_days=14, sort_order=460, icon="upload"),
    ServiceDef("utm_reports", "Отчёты по каналам", "Маркетинг", "Источники заказов и ROI",
               TIER_PRO, dependencies=("pixels_analytics",), sort_order=470),
    ServiceDef("crm", "CRM", "Маркетинг", "Карточка клиента, заметки и история",
               TIER_PRO, dependencies=("customers",), sort_order=480),
    ServiceDef("segments", "Сегменты", "Маркетинг", "Группы по покупкам и активности",
               TIER_PRO, dependencies=("customers",), sort_order=490),
    ServiceDef("nps", "Оценка сервиса", "Маркетинг", "Опрос после заказа",
               TIER_PRO, dependencies=("orders",), sort_order=500),
    ServiceDef("gift_certificates", "Подарочные сертификаты", "Маркетинг", "Продажа и погашение",
               TIER_PRO, dependencies=("online_payments",), sort_order=510),
    ServiceDef("subscriptions", "Регулярные заказы", "Маркетинг", "Подписка на доставку",
               TIER_PRO, dependencies=("online_payments", "delivery"), sort_order=520),
    ServiceDef("referral", "Реферальная программа", "Маркетинг", "Коды и вознаграждения",
               TIER_PRO, dependencies=("loyalty",), sort_order=530),
    ServiceDef("abandoned_cart", "Брошенная корзина", "Маркетинг", "Напоминание о заказе",
               TIER_PRO, dependencies=("customers", "email_marketing"), sort_order=540),
    ServiceDef("upsell", "Рекомендации", "Маркетинг", "«С этим покупают» и допродажа",
               TIER_PRO, dependencies=("catalog",), sort_order=550),

    # ─── Склад и операции ───────────────────────────────────────────
    ServiceDef("inventory", "Складской учёт", "Операции", "Остатки, приход и инвентаризация",
               TIER_PRO, dependencies=("catalog",), sort_order=610, icon="box"),
    ServiceDef("suppliers", "Поставщики", "Операции", "Карточки и условия поставщиков",
               TIER_PRO, dependencies=("inventory",), sort_order=620),
    ServiceDef("purchase_orders", "Закупки", "Операции", "Заявки и приёмка",
               TIER_PRO, dependencies=("suppliers",), sort_order=630),

    # ─── Add-on ─────────────────────────────────────────────────────
    ServiceDef("sms_marketing", "SMS-рассылки", "Add-on", "Акции и уведомления по базе клиентов",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("customers",),
               trial_days=14, sort_order=710, icon="message"),
    ServiceDef("messenger_marketing", "Telegram / Viber", "Add-on", "Рассылки в мессенджерах",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("customers",), sort_order=720),
    ServiceDef("whatsapp", "WhatsApp", "Add-on", "Кнопка и уведомления WhatsApp Business",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("customers",), sort_order=730),
    ServiceDef("multi_branch", "Несколько точек", "Add-on", "Адреса, наличие и отчёты по точкам",
               TIER_ADDON, price_month=Decimal("14.90"), dependencies=("inventory",), sort_order=740),
    ServiceDef("multi_warehouse", "Несколько складов", "Add-on", "Остатки по складам и перемещения",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("inventory",), sort_order=750),
    ServiceDef("integration_1c", "1С", "Add-on", "Обмен товарами, ценами и заказами",
               TIER_ADDON, price_month=Decimal("19.90"), dependencies=("catalog", "orders"), sort_order=760),
    ServiceDef("integration_moysklad", "МойСклад", "Add-on", "Синхронизация каталога и остатков",
               TIER_ADDON, price_month=Decimal("14.90"), dependencies=("catalog",), sort_order=770),
    ServiceDef("fiscalization", "Фискализация", "Add-on", "Чеки и касса",
               TIER_ADDON, price_month=Decimal("19.90"), dependencies=("online_payments",), sort_order=780),
    ServiceDef("marketplaces", "Маркетплейсы", "Add-on", "Выгрузка товаров и заказов",
               TIER_ADDON, price_month=Decimal("19.90"), dependencies=("catalog", "orders"), sort_order=790),
    ServiceDef("custom_domain", "Свой домен", "Add-on", "Подключение домена и SSL",
               TIER_ADDON, price_month=Decimal("5.00"), dependencies=("storefront",), sort_order=800, icon="globe"),
    ServiceDef("premium_templates", "Premium-шаблоны", "Add-on", "Расширенные шаблоны и блоки",
               TIER_ADDON, price_month=Decimal("7.00"), dependencies=("templates_basic",), sort_order=810),
    ServiceDef("extra_storage", "Доп. хранилище", "Add-on", "+10 ГБ для фото и документов",
               TIER_ADDON, price_month=Decimal("5.00"), sort_order=820),
    ServiceDef("ai_copy", "AI-тексты", "Add-on", "Описания товаров и акции",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("catalog",), sort_order=830),
    ServiceDef("ai_photo", "AI-фото", "Add-on", "Удаление фона и улучшение карточек",
               TIER_ADDON, price_month=Decimal("9.90"), dependencies=("catalog",), sort_order=840),
    ServiceDef("ai_forecast", "AI-прогноз", "Add-on", "Прогноз спроса и закупок",
               TIER_ADDON, price_month=Decimal("14.90"), dependencies=("inventory",), sort_order=850),
    ServiceDef("ai_assistant", "AI-помощник", "Add-on", "Подсказки и генерация акций",
               TIER_ADDON, price_month=Decimal("9.90"), sort_order=860),
    ServiceDef("api_webhooks", "API и webhooks", "Add-on", "Доступ к API и события",
               TIER_ADDON, price_month=Decimal("9.90"), sort_order=870),
    ServiceDef("translation", "Мультиязычность", "Add-on", "Второй язык витрины",
               TIER_ADDON, price_month=Decimal("7.00"), dependencies=("storefront",), sort_order=880),
    ServiceDef("audit_export", "Экспорт аудита", "Add-on", "Выгрузка журнала действий",
               TIER_ADDON, price_month=Decimal("5.00"), sort_order=890),
    ServiceDef("white_label", "White-label", "Платформа", "Скрыть бренд платформы",
               TIER_PLATFORM, sort_order=910),
    ServiceDef("dedicated_instance", "Выделенный экземпляр", "Платформа", "Отдельный контейнер и БД",
               TIER_PLATFORM, sort_order=920),
    ServiceDef("sla_priority", "Приоритетный SLA", "Платформа", "Ускоренная поддержка",
               TIER_PLATFORM, sort_order=930),
    ServiceDef("sso", "SSO", "Платформа", "Вход через корпоративный провайдер",
               TIER_PLATFORM, sort_order=940),
)


STATUS_READY = "ready"
STATUS_PARTIAL = "partial"
STATUS_PLANNED = "planned"

STATUS_TITLES = {
    STATUS_READY: "Готово",
    STATUS_PARTIAL: "Частично",
    STATUS_PLANNED: "В разработке",
}

# Что уже работает, а что требует условий или ещё в плане. Это честный статус
# для владельца платформы: по нему видно, что можно продавать уже сегодня.
SERVICE_STATUS: dict[str, tuple[str, str]] = {
    "backup_daily": (STATUS_PARTIAL, "Резервные копии делаются по регламенту; кнопки восстановления в панели пока нет."),
    "online_payments": (STATUS_PARTIAL, "Логика и счёт готовы, но нужен договор эквайринга и ключи провайдера."),
    "custom_domain": (STATUS_PARTIAL, "Домен подключается через поддержку: DNS и SSL настраиваются вручную."),
    "extra_storage": (STATUS_PARTIAL, "Лимит учитывается в тарифе, отдельное хранилище автоматически не выделяется."),
    "audit_export": (STATUS_PARTIAL, "Журнал действий виден в панели, выгрузка файлом ещё не сделана."),
    "preorder": (STATUS_PLANNED, "Предзаказ товара под поставку — в разработке."),
    "certificates": (STATUS_PLANNED, "Сертификаты качества к товару — в разработке."),
    "tasks": (STATUS_PLANNED, "Задачи сотрудникам — следующий шаг после чата."),
    "wholesale": (STATUS_PLANNED, "Вторая цена для оптовиков — в разработке."),
    "push_notifications": (STATUS_PLANNED, "Web-push — в разработке."),
    "landing_builder": (STATUS_PLANNED, "Конструктор страниц — в разработке."),
    "dynamic_pricing": (STATUS_PLANNED, "Правила динамических цен — в разработке."),
    "utm_reports": (STATUS_PLANNED, "Отчёты по каналам — в разработке."),
    "nps": (STATUS_PLANNED, "Оценка сервиса после заказа — в разработке."),
    "gift_certificates": (STATUS_PLANNED, "Подарочные сертификаты — в разработке."),
    "subscriptions": (STATUS_PLANNED, "Регулярные заказы покупателей — в разработке."),
    "referral": (STATUS_PLANNED, "Реферальная программа — в разработке."),
    "messenger_marketing": (STATUS_PLANNED, "Рассылки в Telegram и Viber — в разработке."),
    "whatsapp": (STATUS_PLANNED, "WhatsApp Business — в разработке."),
    "multi_branch": (STATUS_PLANNED, "Несколько торговых точек — в разработке."),
    "multi_warehouse": (STATUS_PLANNED, "Несколько складов — в разработке."),
    "integration_1c": (STATUS_PLANNED, "Обмен с 1С — по спросу, в разработке."),
    "integration_moysklad": (STATUS_PLANNED, "Интеграция с МойСклад — по спросу."),
    "fiscalization": (STATUS_PLANNED, "Фискализация и чеки — нужен провайдер и договор."),
    "marketplaces": (STATUS_PLANNED, "Выгрузка на маркетплейсы — в разработке."),
    "ai_copy": (STATUS_PLANNED, "AI-описания товаров — в разработке."),
    "ai_photo": (STATUS_PLANNED, "AI-обработка фото — в разработке."),
    "ai_forecast": (STATUS_PLANNED, "AI-прогноз спроса — в разработке."),
    "ai_assistant": (STATUS_PLANNED, "AI-помощник — в разработке."),
    "api_webhooks": (STATUS_PLANNED, "Публичный API и webhooks — в разработке."),
    "translation": (STATUS_PLANNED, "Второй язык витрины — в разработке."),
    "white_label": (STATUS_PLANNED, "Скрытие бренда платформы — для тарифа «Платформа»."),
    "dedicated_instance": (STATUS_PLANNED, "Выделенный экземпляр — по запросу, вручную."),
    "sla_priority": (STATUS_PLANNED, "Приоритетный SLA — организационная услуга, в разработке."),
    "sso": (STATUS_PLANNED, "Вход через корпоративный провайдер — в разработке."),
}

# Где владелец настраивает сервис в админке магазина.
SERVICE_SETUP: dict[str, str] = {
    "promo_codes": "/admin/promo-codes",
    "reviews": "/admin/reviews",
    "delivery": "/admin/delivery",
    "pickup_slots": "/admin/delivery",
    "price_tags": "/admin/price-tags",
    "labels": "/admin/barcodes",
    "barcode": "/admin/barcodes",
    "seo_tools": "/admin/settings",
    "pixels_analytics": "/admin/settings",
    "loyalty": "/admin/loyalty",
    "crm": "/admin/crm",
    "segments": "/admin/crm",
    "abandoned_cart": "/admin/carts",
    "upsell": "/admin/upsells",
    "support_chat": "/admin/chat",
    "price_import": "/admin/imports",
    "email_marketing": "/admin/campaigns",
    "sms_marketing": "/admin/campaigns",
    "inventory": "/admin/inventory",
    "suppliers": "/admin/suppliers",
    "purchase_orders": "/admin/suppliers",
    "staff_roles": "/admin/users",
    "order_tracking": "/admin/orders",
    "promo_banners": "/admin/promotions",
    "blog": "/admin/settings",
    "templates_basic": "/admin/settings",
    "premium_templates": "/admin/settings",
    "site_settings": "/admin/settings",
    "basic_reports": "/admin/reports",
}


def service_status(code: str) -> tuple[str, str]:
    return SERVICE_STATUS.get(code, (STATUS_READY, ""))


SERVICE_BY_CODE = {item.code: item for item in SERVICE_CATALOG}
PLAN_BY_CODE = {item.code: item for item in PLANS}


def included_in_plan(service_code: str, plan_code: str) -> bool:
    service = SERVICE_BY_CODE.get(service_code)
    if not service:
        return False
    if service.tier == TIER_FREE:
        return True
    if service.tier in PLAN_ORDER:
        return PLAN_ORDER.get(plan_code, 0) >= PLAN_ORDER[service.tier]
    return False
