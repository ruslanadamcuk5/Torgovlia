"""Генерация QR-кодов для сайта и карточек товаров."""

from io import BytesIO
from urllib.parse import urljoin

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from app.config import settings


def public_url(path: str = "/") -> str:
    base = settings.public_base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def make_qr_png(data: str, size: int = 640, border: int = 4) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b2b33", back_color="white").convert("RGB")
    img = img.resize((size, size))
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def product_url(slug: str) -> str:
    return public_url(f"/fish/{slug}")


def site_url() -> str:
    return public_url("/")
