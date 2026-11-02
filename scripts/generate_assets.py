"""Генерация локальных SVG-иллюстраций и PNG-иконок PWA.

Запуск: python scripts/generate_assets.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "frontend" / "public"
FISH_DIR = PUBLIC / "assets" / "fish"
ICONS = PUBLIC / "icons"
FISH_DIR.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)

PALETTES = {
    "sea": ("#0A3A4A", "#12707C", "#F4E3C0"),
    "river": ("#254B36", "#4E7C52", "#F0E2B6"),
    "smoked": ("#4A2A18", "#9C5527", "#F6D9A8"),
    "seafood": ("#431E2B", "#8A3B4B", "#F7D6C9"),
    "caviar": ("#241733", "#56406E", "#F0D9A8"),
}

PRODUCT_CATEGORY = {
    "seld-atlanticheskaya": "smoked",
    "skumbriya-holodnogo-kopcheniya": "smoked",
    "forel-raduzhnaya": "river",
    "semga-slabosolynaya": "smoked",
    "treska-file": "sea",
    "mintay": "sea",
    "karp-zhivoy": "river",
    "shchuka": "river",
    "okun-morskoy": "sea",
    "kambala": "sea",
    "tunets-steak": "sea",
    "krevetki-tigrovye": "seafood",
    "ikra-lososevaya": "caviar",
    "seld-pryanogo-posola": "smoked",
    "sudak": "river",
}


def fish_svg(slug: str, palette: str) -> str:
    c1, c2, accent = PALETTES[palette]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" role="img" aria-label="Иллюстрация рыбы">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>
    </linearGradient>
    <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".34"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity=".10"/>
    </linearGradient>
    <radialGradient id="glow" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="{accent}" stop-opacity=".30"/>
      <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="600" fill="url(#bg)"/>
  <circle cx="660" cy="90" r="190" fill="url(#glow)"/>
  <circle cx="120" cy="520" r="120" fill="#000000" opacity=".10"/>
  <g stroke="#ffffff" fill="none" opacity=".16" stroke-width="2">
    <circle cx="650" cy="120" r="16"/><circle cx="700" cy="190" r="8"/>
    <circle cx="590" cy="200" r="6"/><circle cx="170" cy="120" r="10"/>
    <circle cx="210" cy="80" r="5"/>
  </g>
  <g transform="translate(390 300) rotate(-7)">
    <path d="M-238 0c60-80 152-120 252-120 94 0 166 42 212 120-46 78-118 120-212 120-100 0-192-40-252-120z" fill="url(#body)" stroke="#ffffff" stroke-opacity=".55" stroke-width="3"/>
    <path d="M-238 0l-96-82v164z" fill="url(#body)" stroke="#ffffff" stroke-opacity=".4" stroke-width="3"/>
    <path d="M-40-118c34 48 34 188 0 236" fill="none" stroke="{accent}" stroke-opacity=".55" stroke-width="4"/>
    <path d="M60-110c26 50 26 170 0 220" fill="none" stroke="#ffffff" stroke-opacity=".22" stroke-width="3"/>
    <path d="M-190 4c30-16 60-16 90 0M-190 30c30-16 60-16 90 0" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width="3"/>
    <path d="M-70-24c34-30 92-30 126 0" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width="3"/>
    <circle cx="168" cy="-30" r="11" fill="#ffffff" fill-opacity=".8"/>
    <circle cx="171" cy="-30" r="5" fill="{c1}"/>
    <path d="M120 26c22 8 46 8 68-2" fill="none" stroke="#ffffff" stroke-opacity=".4" stroke-width="3"/>
  </g>
  <g stroke="{accent}" fill="none" stroke-width="3" opacity=".45">
    <path d="M-20 520c90-32 180 32 270 0s180-32 270 0 180 32 270 0"/>
    <path d="M-20 552c90-32 180 32 270 0s180-32 270 0 180 32 270 0"/>
  </g>
</svg>'''


LOGO = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" role="img" aria-label="Рыбная лавка">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0E4A54"/><stop offset="1" stop-color="#08272E"/>
    </linearGradient>
  </defs>
  <rect width="96" height="96" rx="24" fill="url(#g)"/>
  <circle cx="48" cy="46" r="30" fill="none" stroke="#E9B44C" stroke-opacity=".35" stroke-width="1.5"/>
  <g transform="translate(49 45)">
    <path d="M-25 0c8-11 21-17 35-17 13 0 23 6 29 17-6 11-16 17-29 17-14 0-27-6-35-17z" fill="none" stroke="#E9B44C" stroke-width="2.6"/>
    <path d="M-25 0l-12-10v20z" fill="none" stroke="#E9B44C" stroke-width="2.6" stroke-linejoin="round"/>
    <circle cx="23" cy="-4" r="2.2" fill="#F6F1E7"/>
    <path d="M2-16c5 9 5 23 0 32" fill="none" stroke="#7FC8C0" stroke-width="2"/>
  </g>
  <path d="M24 68c8-5 16 5 24 0s16 5 24 0" fill="none" stroke="#7FC8C0" stroke-width="2.4" stroke-linecap="round"/>
</svg>'''

FAVICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#08272E"/>
  <path d="M14 31c6-7 15-11 24-11 9 0 15 4 19 11-4 7-10 11-19 11-9 0-18-4-24-11z" fill="none" stroke="#E9B44C" stroke-width="2.4"/>
  <path d="M14 31l-7-6v12z" fill="none" stroke="#E9B44C" stroke-width="2.4" stroke-linejoin="round"/>
  <circle cx="45" cy="28" r="1.8" fill="#F6F1E7"/>
  <path d="M18 47c7-4 14 4 21 0s10 2 13 1" fill="none" stroke="#7FC8C0" stroke-width="2" stroke-linecap="round"/>
</svg>'''

HERO = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 760" role="img" aria-label="Свежая рыба">
  <defs>
    <linearGradient id="sea" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0B3F4A"/><stop offset=".55" stop-color="#082A33"/><stop offset="1" stop-color="#061F26"/>
    </linearGradient>
    <linearGradient id="fish1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#F3D79A"/><stop offset="1" stop-color="#D9A441"/>
    </linearGradient>
    <linearGradient id="fish2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7FC8C0"/><stop offset="1" stop-color="#2E7E84"/>
    </linearGradient>
    <radialGradient id="halo" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#E9B44C" stop-opacity=".34"/>
      <stop offset="1" stop-color="#E9B44C" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="900" height="760" rx="40" fill="url(#sea)"/>
  <circle cx="640" cy="220" r="280" fill="url(#halo)"/>
  <g stroke="#7FC8C0" fill="none" opacity=".16" stroke-width="2">
    <circle cx="160" cy="150" r="60"/><circle cx="160" cy="150" r="110"/>
    <circle cx="780" cy="560" r="90"/><circle cx="780" cy="560" r="150"/>
  </g>
  <g opacity=".35" fill="#F6F1E7">
    <circle cx="700" cy="130" r="7"/><circle cx="760" cy="180" r="4"/><circle cx="660" cy="210" r="4"/>
    <circle cx="210" cy="430" r="6"/><circle cx="250" cy="380" r="3"/>
  </g>
  <g transform="translate(470 330) rotate(-8)">
    <path d="M-300 0c78-102 195-152 322-152 120 0 212 54 272 152-60 98-152 152-272 152-127 0-244-50-322-152z" fill="url(#fish1)" fill-opacity=".95"/>
    <path d="M-300 0l-120-100v200z" fill="url(#fish1)" fill-opacity=".95"/>
    <path d="M-60-150c46 70 46 230 0 300" fill="none" stroke="#08272E" stroke-opacity=".18" stroke-width="6"/>
    <path d="M60-140c36 72 36 208 0 280" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width="5"/>
    <path d="M-238 10c42-22 84-22 126 0M-238 48c42-22 84-22 126 0" fill="none" stroke="#08272E" stroke-opacity=".14" stroke-width="5"/>
    <circle cx="212" cy="-38" r="15" fill="#08272E"/>
    <circle cx="217" cy="-42" r="5" fill="#F6F1E7"/>
    <path d="M150 34c28 10 58 10 86-4" fill="none" stroke="#08272E" stroke-opacity=".22" stroke-width="5"/>
  </g>
  <g transform="translate(250 600) rotate(6) scale(.42)">
    <path d="M-300 0c78-102 195-152 322-152 120 0 212 54 272 152-60 98-152 152-272 152-127 0-244-50-322-152z" fill="url(#fish2)"/>
    <path d="M-300 0l-120-100v200z" fill="url(#fish2)"/>
    <circle cx="212" cy="-38" r="14" fill="#061F26"/>
  </g>
  <g stroke="#7FC8C0" fill="none" stroke-width="4" opacity=".5">
    <path d="M40 660c70-26 140 26 210 0s140-26 210 0 140 26 210 0 140-26 210 0"/>
    <path d="M40 700c70-26 140 26 210 0s140-26 210 0 140 26 210 0 140-26 210 0"/>
  </g>
  <g fill="none" stroke="#F3D79A" stroke-width="2.5" opacity=".6">
    <path d="M90 90h70M90 90v70"/><path d="M810 690h-70M810 690v-70"/>
  </g>
</svg>'''


def rounded_icon(size: int, padding_ratio: float = 0.0) -> Image.Image:
    scale = 4
    canvas = size * scale
    img = Image.new("RGB", (canvas, canvas), "#F6F1E7")
    draw = ImageDraw.Draw(img)
    pad = int(canvas * padding_ratio)
    box = (pad, pad, canvas - pad, canvas - pad)
    radius = int((box[2] - box[0]) * 0.22)
    draw.rounded_rectangle(box, radius=radius, fill="#08272E")

    cx = canvas // 2
    cy = int(canvas * 0.47)
    unit = (box[2] - box[0]) / 100.0

    # декоративные круги
    draw.ellipse(
        (cx - 34 * unit, cy - 34 * unit, cx + 34 * unit, cy + 34 * unit),
        outline="#16464F",
        width=max(2, int(1.2 * unit)),
    )
    draw.ellipse(
        (cx - 44 * unit, cy - 44 * unit, cx + 44 * unit, cy + 44 * unit),
        outline="#103A43",
        width=max(2, int(1.0 * unit)),
    )

    # рыба
    gold = "#E9B44C"
    body = (cx - 26 * unit, cy - 14 * unit, cx + 24 * unit, cy + 14 * unit)
    draw.ellipse(body, fill=gold)
    draw.polygon(
        [
            (int(cx - 26 * unit), cy),
            (int(cx - 40 * unit), int(cy - 16 * unit)),
            (int(cx - 40 * unit), int(cy + 16 * unit)),
        ],
        fill=gold,
    )
    draw.ellipse(
        (int(cx + 11 * unit), int(cy - 5 * unit), int(cx + 17 * unit), int(cy + 1 * unit)),
        fill="#08272E",
    )
    draw.arc(
        (int(cx - 6 * unit), int(cy - 14 * unit), int(cx + 12 * unit), int(cy + 14 * unit)),
        start=280,
        end=80,
        fill="#0B3F4A",
        width=max(2, int(1.6 * unit)),
    )
    # волны
    wave_y = int(canvas * 0.72)
    for i in range(3):
        points = []
        for step in range(0, 101, 2):
            x = box[0] + (box[2] - box[0]) * step / 100
            y = wave_y + i * int(4 * unit) + int(3 * unit) * (1 if (step // 8) % 2 == 0 else -1)
            points.append((x, y))
        draw.line(points, fill="#7FC8C0" if i == 0 else "#2F6E73", width=max(2, int(1.4 * unit)))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    (PUBLIC / "assets").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "assets" / "logo.svg").write_text(LOGO, encoding="utf-8")
    (PUBLIC / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    (PUBLIC / "assets" / "hero-fish.svg").write_text(HERO, encoding="utf-8")

    for slug, palette in PRODUCT_CATEGORY.items():
        (FISH_DIR / f"{slug}.svg").write_text(fish_svg(slug, palette), encoding="utf-8")

    rounded_icon(192).save(ICONS / "icon-192.png")
    rounded_icon(512).save(ICONS / "icon-512.png")
    rounded_icon(512, padding_ratio=0.12).save(ICONS / "maskable-512.png")
    rounded_icon(180).save(ICONS / "apple-touch-icon.png")

    print("Готово: SVG-иллюстрации и PNG-иконки созданы")


if __name__ == "__main__":
    main()
