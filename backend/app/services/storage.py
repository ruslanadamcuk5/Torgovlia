"""Загрузка изображений товаров и баннеров."""

import uuid
from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.tenancy import current_tenant


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 1800
# Защита от «бомб» декомпрессии: 50 Мпикс достаточно для фото с телефона.
Image.MAX_IMAGE_PIXELS = 50_000_000


def save_image(upload: UploadFile) -> dict:
    if not upload.content_type or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Можно загружать только изображения (JPEG, PNG, WebP)")

    limit = settings.upload_max_mb * 1024 * 1024
    raw = upload.file.read(limit + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Файл пустой")
    if len(raw) > limit:
        raise HTTPException(status_code=400, detail=f"Файл больше {settings.upload_max_mb} МБ")

    try:
        image = Image.open(BytesIO(raw))
        image_format = image.format
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="Не удалось прочитать изображение") from exc

    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail="Поддерживаются JPEG, PNG и WebP")

    if getattr(image, "is_animated", False):
        image.seek(0)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)

    filename = f"{uuid.uuid4().hex}.webp"
    # Файлы раскладываем по магазинам: так проще считать место, делать выборочный
    # бэкап и удалять данные арендатора при расторжении договора.
    tenant = current_tenant()
    folder = settings.media_path / "uploads"
    prefix = "uploads"
    if tenant:
        folder = folder / tenant.slug
        prefix = f"uploads/{tenant.slug}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    image.save(target, format="WEBP", quality=88, method=6)

    return {
        "url": f"/media/{prefix}/{filename}",
        "filename": filename,
        "size": target.stat().st_size,
    }
