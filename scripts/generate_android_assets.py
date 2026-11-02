"""
Генерация брендированных иконок и splash-экранов Android из PWA-иконки.

Запуск (из корня репозитория):
    backend/.venv/Scripts/python.exe scripts/generate_android_assets.py

Требуется Pillow. Скрипт перезаписывает только ресурсы лаунчера и splash
в frontend/android/app/src/main/res, не трогая код приложения.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "public" / "icons" / "icon-512.png"
RES = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"

DARK = (8, 39, 46, 255)
CREAM = (246, 241, 231, 255)
GOLD = (233, 180, 76, 255)

ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
FOREGROUND_SIZES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
SPLASH_SIZES = {
    "drawable": (480, 800),
    "drawable-land-mdpi": (480, 320),
    "drawable-land-hdpi": (800, 480),
    "drawable-land-xhdpi": (1280, 720),
    "drawable-land-xxhdpi": (1600, 960),
    "drawable-land-xxxhdpi": (1920, 1280),
    "drawable-port-mdpi": (320, 480),
    "drawable-port-hdpi": (480, 800),
    "drawable-port-xhdpi": (720, 1280),
    "drawable-port-xxhdpi": (960, 1600),
    "drawable-port-xxxhdpi": (1280, 1920),
}


def rounded(size: int, radius_ratio: float = 0.22) -> Image.Image:
    image = Image.open(SOURCE).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255
    )
    image.putalpha(mask)
    return image


def circular(size: int) -> Image.Image:
    image = Image.open(SOURCE).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    image.putalpha(mask)
    return image


def foreground(size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = int(size * 0.82)
    icon = rounded(inner)
    offset = (size - inner) // 2
    canvas.alpha_composite(icon, (offset, offset))
    return canvas


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def splash(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), DARK)
    draw = ImageDraw.Draw(image)
    short = min(width, height)
    icon_size = int(short * 0.34)
    icon = rounded(icon_size)
    image.paste(icon, ((width - icon_size) // 2, int(height * 0.34) - icon_size // 2), icon)

    title_size = max(20, int(short * 0.055))
    subtitle_size = max(11, int(short * 0.026))
    title_font = font(title_size, bold=True)
    subtitle_font = font(subtitle_size)

    title = "РЫБНАЯ ЛАВКА"
    subtitle = "Барановичи · рынок «Алексеевский»"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    title_y = int(height * 0.34) + icon_size // 2 + int(short * 0.045)
    draw.text(((width - (title_box[2] - title_box[0])) / 2, title_y), title, font=title_font, fill=GOLD)
    draw.text(
        ((width - (subtitle_box[2] - subtitle_box[0])) / 2, title_y + title_size + int(short * 0.018)),
        subtitle,
        font=subtitle_font,
        fill=CREAM,
    )
    return image


def main() -> None:
    for density, size in ICON_SIZES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        rounded(size).save(folder / "ic_launcher.png")
        circular(size).save(folder / "ic_launcher_round.png")
        foreground(FOREGROUND_SIZES[density]).save(folder / "ic_launcher_foreground.png")

    for folder_name, (width, height) in SPLASH_SIZES.items():
        folder = RES / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        splash(width, height).save(folder / "splash.png", optimize=True)

    (RES / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <color name="ic_launcher_background">#08272E</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    print("Android icons and splash screens generated.")


if __name__ == "__main__":
    main()
