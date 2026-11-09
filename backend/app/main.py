import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api import (
    account,
    admin,
    auth,
    billing_admin,
    gift_certificates,
    subscriptions,
    platform,
    platform_audit,
    platform_auth,
    platform_incidents,
    platform_analytics,
    platform_settings,
    platform_team,
    platform_ops,
    public,
    seller,
    services_admin,
    signup,
    status_page,
    tasks_admin,
)
from app.config import BASE_DIR, settings
from app.db import get_db, init_db
from app.seed import seed_all
from app.services.settings import settings_for_tenant
from app.tenancy import TenantMiddleware, current_tenant, tenant_by_slug


logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("rybnaya")


def _check_production_settings() -> None:
    """Не даём запустить production с настройками для разработки."""
    if not settings.is_production:
        return
    problems: list[str] = []
    if len(settings.secret_key) < 32 or "change" in settings.secret_key.lower():
        problems.append("SECRET_KEY должен быть случайным и содержать не менее 32 символов")
    if settings.debug:
        problems.append("DEBUG должен быть false")
    if not settings.public_base_url.startswith("https://"):
        problems.append("PUBLIC_BASE_URL должен начинаться с https://")
    if problems:
        raise RuntimeError("Некорректная production-конфигурация: " + "; ".join(problems))
    if settings.sms_provider.lower() == "console":
        log.error("SMS_PROVIDER=console в production: коды не будут доставлены покупателям!")
    if settings.admin_password == "ChangeMe123!":
        log.warning("Смените ADMIN_PASSWORD после первого запуска!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_production_settings()
    init_db()
    seed_all()
    log.info("Сервер запущен. Публичный адрес: %s", settings.public_base_url)
    yield


app = FastAPI(
    title="Платформа интернет-магазинов — API",
    description=(
        "API витрины и админки магазина: каталог, статьи, заказы с самовывозом, "
        "SMS-подтверждение номера, администрирование и QR-коды."
    ),
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(TenantMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(self)")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error.get("loc", []) if part not in ("body", "query"))
        errors.append({"field": field, "message": error.get("msg", "Некорректное значение")})
    first = errors[0]["message"] if errors else "Проверьте заполнение полей"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": first, "errors": errors},
    )


app.include_router(public.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(seller.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(signup.router, prefix="/api")
app.include_router(platform_auth.router, prefix="/api")
app.include_router(platform.router, prefix="/api")
app.include_router(platform_analytics.router, prefix="/api")
app.include_router(platform_ops.router, prefix="/api")
app.include_router(platform_audit.router, prefix="/api")
app.include_router(platform_incidents.router, prefix="/api")
app.include_router(platform_settings.router, prefix="/api")
app.include_router(platform_team.router, prefix="/api")
app.include_router(status_page.router, prefix="/api")
app.include_router(services_admin.router, prefix="/api")
app.include_router(tasks_admin.router, prefix="/api")
app.include_router(gift_certificates.admin_router, prefix="/api")
app.include_router(gift_certificates.public_router, prefix="/api")
app.include_router(subscriptions.admin_router, prefix="/api")
app.include_router(subscriptions.account_router, prefix="/api")
app.include_router(billing_admin.router, prefix="/api")

app.mount("/media", StaticFiles(directory=str(settings.media_path)), name="media")


@app.get("/api/health", tags=["Служебные"], summary="Проверка работоспособности")
def health():
    return {"status": "ok", "environment": settings.environment, "version": app.version}


@app.get("/sitemap.xml", include_in_schema=False)
def root_sitemap(request: Request, db: Session = Depends(get_db)):
    """Карта сайта для основного домена магазина."""
    if current_tenant() is None:
        return JSONResponse(status_code=404, content={"detail": "Магазин не найден"})
    base = public.public_base_url(request)
    return Response(
        content=public.build_sitemap(db, base),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@app.get("/robots.txt", include_in_schema=False)
def root_robots(request: Request, db: Session = Depends(get_db)):
    if current_tenant() is None:
        return JSONResponse(status_code=404, content={"detail": "Магазин не найден"})
    base = public.public_base_url(request)
    return Response(
        content=public.build_robots(db, base),
        media_type="text/plain",
        headers={"Cache-Control": "public, max-age=1800"},
    )


def _shop_seo(request: Request, db: Session, slug: str):
    tenant = tenant_by_slug(db, slug)
    if not tenant:
        return None, None, None
    base = f"{str(request.base_url).rstrip('/')}/shop/{tenant.slug}"
    conf = settings_for_tenant(db, tenant.id)
    return tenant, base, conf


@app.get("/shop/{slug}/sitemap.xml", include_in_schema=False)
def shop_sitemap(slug: str, request: Request, db: Session = Depends(get_db)):
    tenant, base, conf = _shop_seo(request, db, slug)
    if not tenant or not base:
        return JSONResponse(status_code=404, content={"detail": "Магазин не найден"})
    return Response(
        content=public.build_sitemap(db, base, tenant.id, conf),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@app.get("/shop/{slug}/robots.txt", include_in_schema=False)
def shop_robots(slug: str, request: Request, db: Session = Depends(get_db)):
    tenant, base, conf = _shop_seo(request, db, slug)
    if not tenant or not base:
        return JSONResponse(status_code=404, content={"detail": "Магазин не найден"})
    return Response(
        content=public.build_robots(db, base, conf),
        media_type="text/plain",
        headers={"Cache-Control": "public, max-age=1800"},
    )


FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Раздача собранного React-приложения с поддержкой клиентских маршрутов."""
    if full_path.startswith(("api/", "media/")):
        return JSONResponse(status_code=404, content={"detail": "Не найдено"})
    if not FRONTEND_DIST.exists():
        return JSONResponse(
            status_code=200,
            content={
                "message": "API работает. Frontend не собран: выполните npm run build в папке frontend.",
                "docs": "/api/docs",
            },
        )
    target = (FRONTEND_DIST / full_path).resolve()
    try:
        target.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        return JSONResponse(status_code=404, content={"detail": "Не найдено"})
    if full_path and target.is_file():
        if full_path.startswith("assets/"):
            # Имена файлов содержат хеш сборки — их можно кешировать надолго.
            headers = {"Cache-Control": "public, max-age=31536000, immutable"}
        elif full_path in {"sw.js", "version.json", "manifest.webmanifest", "index.html"}:
            # Эти файлы должны обновляться сразу после деплоя, иначе браузер
            # продолжает открывать старую сборку и показывает устаревшие экраны.
            headers = {"Cache-Control": "no-cache, must-revalidate"}
        else:
            headers = {"Cache-Control": "public, max-age=3600"}
        return FileResponse(target, headers=headers)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache, must-revalidate"})
    return JSONResponse(status_code=404, content={"detail": "Не найдено"})
