import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import account, admin, auth, platform, platform_auth, public, seller, services_admin
from app.config import BASE_DIR, settings
from app.db import init_db
from app.seed import seed_all
from app.tenancy import TenantMiddleware


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
    title="Рыбная лавка — API",
    description=(
        "API сайта и мобильного приложения рыбного павильона: каталог, статьи, "
        "бронирование с самовывозом, SMS-подтверждение номера, администрирование и QR-коды."
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
app.include_router(platform_auth.router, prefix="/api")
app.include_router(platform.router, prefix="/api")
app.include_router(services_admin.router, prefix="/api")

app.mount("/media", StaticFiles(directory=str(settings.media_path)), name="media")


@app.get("/api/health", tags=["Служебные"], summary="Проверка работоспособности")
def health():
    return {"status": "ok", "environment": settings.environment, "version": app.version}


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
        return FileResponse(target)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(status_code=404, content={"detail": "Не найдено"})
