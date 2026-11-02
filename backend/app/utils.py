import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(value: str, fallback: str = "item") -> str:
    value = (value or "").strip().lower()
    value = "".join(TRANSLIT.get(ch, ch) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80] or fallback


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def qty(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def as_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)))


def iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def local_today() -> date:
    # Беларусь: UTC+3, переход на летнее время не применяется
    from datetime import timezone

    return (datetime.now(timezone.utc) + timedelta(hours=3)).date()


def local_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc) + timedelta(hours=3)


def human_date(value: date) -> str:
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"{value.day} {months[value.month - 1]}"


def safe_filename(name: str) -> str:
    name = (name or "file").lower()
    name = "".join(TRANSLIT.get(ch, ch) for ch in name)
    name = re.sub(r"[^a-z0-9._-]+", "-", name).strip("-._")
    return name[:80] or "file"
