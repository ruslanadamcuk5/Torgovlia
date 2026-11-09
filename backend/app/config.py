from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Torgovlia"
    environment: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-me-in-production-please-0000"
    public_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,capacitor://localhost"

    # ─── Платформа (multi-tenancy) ──────────────────────────────────
    platform_name: str = "Torgovlia"
    # Домен, на котором живёт сайт продаж и панель платформы.
    platform_host: str = "localhost"
    # Поддомены арендаторов: <slug>.<platform_base_domain>
    platform_base_domain: str = "localhost"
    # Арендатор по умолчанию для локальной разработки и старых ссылок.
    default_tenant_slug: str = "rybnaya"
    default_tenant_name: str = "Магазин"
    # Разрешать выбор арендатора заголовком X-Tenant-Slug (только не production).
    tenant_header_enabled: bool = True
    # Демо-режим одного origin: витрины открываются по /shop/<slug> с заголовком
    # X-Tenant-Slug. Только для демонстрационного стенда, не для клиентов.
    demo_mode: bool = False
    # Демо-магазин, который показываем на сайте продаж: витрина + админка.
    demo_tenant_slug: str = "odezhda"
    demo_admin_phone: str = "+375291112288"
    demo_admin_password: str = "ChangeMe123!"
    # Как часто возвращать демо к исходному состоянию (0 — не сбрасывать).
    demo_reset_hours: int = 24
    # Наполнять флагманское демо полным контентом (товары, заказы, отзывы).
    demo_content: bool = True

    database_url: str = "sqlite:///./data/rybnaya.db"
    media_root: str = "media"
    upload_max_mb: int = 8

    access_token_minutes: int = 60 * 24 * 7
    phone_token_minutes: int = 15

    sms_provider: str = "console"
    sms_expose_code: bool = True
    sms_api_url: str = "https://api.sms.by/api/v1/message/send"
    sms_api_token: str = ""
    sms_login: str = ""
    sms_password: str = ""
    sms_sender: str = ""
    sms_code_ttl_minutes: int = 5
    sms_cooldown_seconds: int = 60
    sms_max_per_hour: int = 5

    admin_phone: str = "+375291112233"
    admin_password: str = "ChangeMe123!"
    admin_name: str = "Владелец"

    platform_admin_phone: str = "+375291110000"
    platform_admin_password: str = "ChangeMe123!"
    platform_admin_name: str = "Владелец платформы"

    # Оповещения платформы в Telegram (необязательно).
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Почта для уведомлений магазинов (необязательно).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True

    seed_demo: bool = True
    seed_catalog: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def media_path(self) -> Path:
        path = Path(self.media_root)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        (path / "uploads").mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
