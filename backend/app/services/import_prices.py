"""Импорт прайсов из CSV, Excel (.xlsx), писем (.eml) и вставленного текста."""

from __future__ import annotations

import csv
import difflib
import html
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email import message_from_bytes
from email import policy as email_policy
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, PriceImport, Product
from app.services import barcode as barcode_service
from app.services.inventory import KIND_ADJUST, apply_move
from app.tenancy import tenant_get
from app.utils import money, qty, slugify


MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_ROWS = 2000
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


@dataclass
class PriceRow:
    line: int
    title: str = ""
    price: Decimal | None = None
    stock: Decimal | None = None
    barcode: str = ""
    unit: str | None = None
    category: str = ""
    sku: str = ""
    raw: list[str] = field(default_factory=list)


@dataclass
class ParsedPrice:
    source: str
    filename: str
    headers: list[str] = field(default_factory=list)
    rows: list[PriceRow] = field(default_factory=list)
    delimiter: str = ""
    warnings: list[str] = field(default_factory=list)


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("название", "наименование", "товар", "продукт", "позиция", "name", "title"),
    "price": ("цена", "стоимость", "розница", "price", "цена byn", "цена руб"),
    "stock": ("остаток", "количество", "кол во", "склад", "stock", "qty", "наличие"),
    "barcode": ("штрихкод", "штрих код", "баркод", "barcode", "ean", "ean13", "штрих код ean"),
    "unit": ("единица", "ед изм", "единица измерения", "unit"),
    "category": ("категория", "группа", "раздел", "category"),
    "sku": ("артикул", "sku", "код поставщика", "код товара", "vendor code", "код"),
}


def _norm(value: str) -> str:
    text = (value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


def _norm_title(value: str) -> str:
    return _norm(value)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "utf-16"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_decimal(value: str) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    text = text.replace("\u00a0", " ").replace(" ", "")
    text = re.sub(r"(?i)(byn|byr|руб\.?|р\.?|rub|eur|usd|€|\$)", "", text)
    text = text.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group())
    except InvalidOperation:
        return None


def parse_money(value: str) -> Decimal | None:
    amount = _parse_decimal(value)
    if amount is None or amount < 0 or amount > 100000:
        return None
    return money(amount)


def parse_quantity(value: str) -> Decimal | None:
    amount = _parse_decimal(value)
    if amount is None or amount < 0 or amount > 1000000:
        return None
    return qty(amount)


def parse_unit(value: str) -> str | None:
    text = _norm(value)
    if not text:
        return None
    if text in ("кг", "kg", "килограмм", "килограммы", "kg."):
        return "kg"
    if text in ("шт", "штука", "штуки", "piece", "pcs", "ед", "единица"):
        return "piece"
    if "кг" in text or "килограм" in text:
        return "kg"
    if "шт" in text or text.startswith("ед"):
        return "piece"
    return None


def _column_index(ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", (ref or "").upper())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return max(index - 1, 0)


def _xlsx_rows(data: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Файл Excel повреждён или это не .xlsx") from exc

    with archive:
        names = archive.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{SHEET_NS}}}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{{{SHEET_NS}}}t")))

        sheet_names = sorted(
            (name for name in names if re.match(r"xl/worksheets/sheet\d+\.xml$", name)),
            key=lambda name: int(re.search(r"(\d+)", Path(name).stem).group(1)),
        )
        if not sheet_names:
            raise ValueError("В файле Excel нет листов")
        root = ElementTree.fromstring(archive.read(sheet_names[0]))

        rows: list[list[str]] = []
        for row in root.findall(f".//{{{SHEET_NS}}}sheetData/{{{SHEET_NS}}}row"):
            values: list[str] = []
            for cell in row.findall(f"{{{SHEET_NS}}}c"):
                position = _column_index(cell.get("r", ""))
                while len(values) <= position:
                    values.append("")
                kind = cell.get("t")
                text = ""
                if kind == "inlineStr":
                    text = "".join(node.text or "" for node in cell.iter(f"{{{SHEET_NS}}}t"))
                else:
                    node = cell.find(f"{{{SHEET_NS}}}v")
                    if node is not None and node.text is not None:
                        text = node.text
                        if kind == "s" and text.isdigit() and int(text) < len(shared):
                            text = shared[int(text)]
                values[position] = _cell_text(text)
            if any(value for value in values):
                rows.append(values)
        return rows


def _email_content(data: bytes) -> tuple[str, tuple[str, bytes] | None]:
    """Возвращает текст письма и вложение (имя, содержимое), если оно есть."""
    message = message_from_bytes(data, policy=email_policy.default)
    for part in message.walk():
        filename = part.get_filename() or ""
        suffix = Path(filename).suffix.lower()
        if suffix in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm"):
            payload = part.get_payload(decode=True) or b""
            if payload:
                return "", (filename, payload)

    for part in message.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace"), None
            except LookupError:
                return payload.decode("utf-8", errors="replace"), None

    for part in message.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                markup = payload.decode(charset, errors="replace")
            except LookupError:
                markup = payload.decode("utf-8", errors="replace")
            text = re.sub(r"<(br|/p|/tr|/div)[^>]*>", "\n", markup, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            return html.unescape(text), None
    raise ValueError("В письме не найден текст или вложение с прайсом")


def _detect_delimiter(lines: list[str]) -> str:
    sample = "\n".join(lines[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=";\t,|").delimiter
    except csv.Error:
        counts = {
            delimiter: sum(line.count(delimiter) for line in lines[:20])
            for delimiter in (";", "\t", ",", "|")
        }
        best = max(counts, key=counts.get)
        return best if counts[best] else ";"


def _read_delimited(text: str) -> tuple[list[list[str]], str, list[str]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        raise ValueError("Текст прайса пустой")
    while lines and re.match(r"(?i)^(from|to|subject|date|cc|bcc|sent):", lines[0].strip()):
        lines.pop(0)
    if not lines:
        raise ValueError("В письме нет строк с товарами")

    delimiter = _detect_delimiter(lines)
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows = [[_cell_text(cell) for cell in row] for row in reader]
    rows = [row for row in rows if any(row)]
    if not rows:
        raise ValueError("В прайсе нет строк")
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows], delimiter, lines


def _header_map(row: list[str]) -> dict[str, int]:
    scores: dict[str, tuple[int, int]] = {}
    for index, cell in enumerate(row):
        value = _norm(cell)
        if not value:
            continue
        for key, aliases in HEADER_ALIASES.items():
            best = 0
            for alias in aliases:
                if value == alias:
                    best = max(best, 3)
                elif value.startswith(alias + " ") or value.endswith(" " + alias):
                    best = max(best, 2)
                elif alias in value:
                    best = max(best, 1)
            if best and key == "price":
                if any(word in value for word in ("закуп", "опт", "приход", "себесто")):
                    best = 0
                if any(word in value for word in ("розниц", "продаж", "прайс")):
                    best += 1
            if best:
                current = scores.get(key)
                if current is None or best > current[0]:
                    scores[key] = (best, index)
    return {key: index for key, (score, index) in scores.items() if score > 0}


def _looks_like_header(row: list[str]) -> bool:
    return len(_header_map(row)) >= 2


def _infer_map(rows: list[list[str]]) -> dict[str, int]:
    """Эвристика для прайсов без шапки: код, цена, остаток и название."""
    if not rows:
        return {}
    width = max(len(row) for row in rows)
    columns: dict[int, list[str]] = {
        index: [row[index] for row in rows if index < len(row) and row[index].strip()]
        for index in range(width)
    }
    mapping: dict[str, int] = {}

    barcode_index = None
    for index, values in columns.items():
        if not values:
            continue
        digits = [re.sub(r"\D", "", value) for value in values]
        if sum(1 for value in digits if 8 <= len(value) <= 14) >= max(1, int(len(values) * 0.7)):
            barcode_index = index
            mapping["barcode"] = index
            break

    numbers: list[tuple[int, int, Decimal]] = []
    for index, values in columns.items():
        if index == barcode_index or not values:
            continue
        parsed = [parse_money(value) for value in values]
        good = [value for value in parsed if value is not None]
        if len(good) >= max(1, int(len(values) * 0.6)):
            numbers.append((index, len(good), max(good)))

    if numbers:
        price_index = max(numbers, key=lambda item: (item[2], item[1]))[0]
        mapping["price"] = price_index
        remaining = [item for item in numbers if item[0] != price_index]
        if remaining:
            mapping["stock"] = max(remaining, key=lambda item: item[1])[0]

    text_columns = [
        (index, sum(len(value) for value in values) / len(values))
        for index, values in columns.items()
        if values and index not in mapping
    ]
    if text_columns:
        mapping["title"] = max(text_columns, key=lambda item: item[1])[0]
    return mapping


def _rows_from_matrix(matrix: list[list[str]], source: str, filename: str, delimiter: str = "") -> ParsedPrice:
    if not matrix:
        raise ValueError("В прайсе нет данных")
    headers: list[str] = []
    mapping: dict[str, int] = {}
    start = 0
    if _looks_like_header(matrix[0]):
        headers = matrix[0]
        mapping = _header_map(matrix[0])
        start = 1
    else:
        mapping = _infer_map(matrix[:40])

    if "title" not in mapping and "barcode" not in mapping:
        raise ValueError(
            "Не удалось распознать колонки. Добавьте шапку: Название, Цена, Остаток, Штрихкод."
        )

    rows: list[PriceRow] = []
    warnings: list[str] = []
    for offset, cells in enumerate(matrix[start:], start=start + 1):
        if not any(str(cell).strip() for cell in cells):
            continue
        get = lambda key: cells[mapping[key]].strip() if key in mapping and mapping[key] < len(cells) else ""
        title = get("title")
        barcode = re.sub(r"\D", "", get("barcode"))
        sku = get("sku")
        if not barcode and sku:
            digits = re.sub(r"\D", "", sku)
            if len(digits) in (8, 12, 13):
                barcode = digits
        price = parse_money(get("price"))
        stock = parse_quantity(get("stock"))
        unit = parse_unit(get("unit"))
        category = get("category")
        if not title and not barcode:
            continue
        if len(barcode) not in (8, 12, 13):
            barcode = ""
        if price is None and stock is None:
            warnings.append(f"Строка {offset}: нет цены и остатка")
        rows.append(
            PriceRow(
                line=offset,
                title=title[:160],
                price=price,
                stock=stock,
                barcode=barcode,
                unit=unit,
                category=category[:120],
                sku=sku[:80],
                raw=cells,
            )
        )
        if len(rows) >= MAX_ROWS:
            warnings.append(f"Взяты первые {MAX_ROWS} строк")
            break
    if not rows:
        raise ValueError("В прайсе не найдено ни одной строки с товаром")
    return ParsedPrice(
        source=source,
        filename=filename,
        headers=headers or [f"Колонка {index + 1}" for index in range(len(matrix[0]))],
        rows=rows,
        delimiter=delimiter,
        warnings=warnings,
    )


def parse_file(filename: str, data: bytes) -> ParsedPrice:
    if not data:
        raise ValueError("Файл пустой")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Файл больше 8 МБ")
    suffix = Path(filename or "").suffix.lower()

    if suffix == ".eml":
        text, attachment = _email_content(data)
        if attachment:
            attachment_name, payload = attachment
            parsed = parse_file(attachment_name, payload)
            parsed.source = "eml"
            parsed.filename = filename or attachment_name
            return parsed
        matrix, delimiter, _ = _read_delimited(text)
        return _rows_from_matrix(matrix, "eml", filename or "письмо.eml", delimiter)

    if suffix in (".xlsx", ".xlsm"):
        return _rows_from_matrix(_xlsx_rows(data), "xlsx", filename)

    if suffix in (".xls",):
        raise ValueError("Старый формат .xls не поддерживается. Сохраните файл как .xlsx или .csv")

    text = _decode(data)
    matrix, delimiter, _ = _read_delimited(text)
    source = "csv" if suffix in (".csv", ".tsv") else "text"
    return _rows_from_matrix(matrix, source, filename or "прайс", delimiter)


def parse_text(text: str, filename: str = "Вставленный текст") -> ParsedPrice:
    matrix, delimiter, _ = _read_delimited(text)
    return _rows_from_matrix(matrix, "text", filename, delimiter)


def _category_map(db: Session) -> dict[str, Category]:
    return {_norm(category.title): category for category in db.scalars(select(Category)).all()}


def _find_category(db: Session, row: PriceRow, fallback_id: int | None) -> Category | None:
    if fallback_id:
        category = tenant_get(db, Category, fallback_id)
        if category:
            return category
    if row.category:
        category = _category_map(db).get(_norm(row.category))
        if category:
            return category
    return None


def _product_indexes(db: Session) -> tuple[dict[str, Product], dict[str, Product], dict[str, Product], list[tuple[str, Product]]]:
    products = db.scalars(select(Product)).all()
    by_barcode = {product.barcode: product for product in products if product.barcode}
    by_slug = {product.slug: product for product in products}
    by_title = {_norm_title(product.title): product for product in products}
    titles = [(key, product) for key, product in by_title.items() if len(key) >= 4]
    return by_barcode, by_slug, by_title, titles


def _match_product(
    row: PriceRow,
    by_barcode: dict[str, Product],
    by_slug: dict[str, Product],
    by_title: dict[str, Product],
    titles: list[tuple[str, Product]],
) -> tuple[Product | None, float, str]:
    if row.barcode and row.barcode in by_barcode:
        return by_barcode[row.barcode], 1.0, "штрихкод"
    if row.sku:
        product = by_slug.get(slugify(row.sku, fallback=""))
        if product:
            return product, 1.0, "артикул"
    key = _norm_title(row.title)
    if key and key in by_title:
        return by_title[key], 1.0, "название"
    if len(key) >= 4 and titles:
        keys = [item[0] for item in titles]
        matches = difflib.get_close_matches(key, keys, n=1, cutoff=0.84)
        if matches:
            score = difflib.SequenceMatcher(None, key, matches[0]).ratio()
            return by_title[matches[0]], round(score, 3), "похожее название"
    return None, 0.0, ""


def preview(db: Session, parsed: ParsedPrice) -> dict:
    by_barcode, by_slug, by_title, titles = _product_indexes(db)
    rows = []
    matched = 0
    new = 0
    invalid = 0
    for row in parsed.rows:
        product, score, reason = _match_product(row, by_barcode, by_slug, by_title, titles)
        if product:
            matched += 1
            status = "matched"
            message = f"Совпадение: {reason}" + (f" · {int(score * 100)}%" if score < 1 else "")
        elif row.title and row.price is not None:
            new += 1
            status = "new"
            message = "Новый товар — можно создать"
        else:
            invalid += 1
            status = "invalid"
            message = "Нужны название и цена" if not row.title else "Не указана цена"
        rows.append(
            {
                "line": row.line,
                "title": row.title,
                "price": float(row.price) if row.price is not None else None,
                "stock": float(row.stock) if row.stock is not None else None,
                "barcode": row.barcode,
                "unit": row.unit,
                "category": row.category,
                "status": status,
                "message": message,
                "product_id": product.id if product else None,
                "product_title": product.title if product else "",
                "score": score,
            }
        )
    return {
        "source": parsed.source,
        "filename": parsed.filename,
        "delimiter": parsed.delimiter,
        "headers": parsed.headers,
        "total": len(rows),
        "matched": matched,
        "new": new,
        "invalid": invalid,
        "warnings": parsed.warnings,
        "rows": rows,
    }


def _unique_slug(db: Session, title: str) -> str:
    base = slugify(title, fallback="tovar")
    slug = base
    index = 2
    while db.scalar(select(Product.id).where(Product.slug == slug)):
        slug = f"{base}-{index}"
        index += 1
    return slug


def apply(db: Session, payload, actor: str) -> PriceImport:
    by_barcode, by_slug, by_title, titles = _product_indexes(db)
    updated = 0
    created = 0
    skipped = 0
    errors = 0
    messages: list[str] = []

    for row in payload.rows:
        product = tenant_get(db, Product, row.product_id) if row.product_id else None
        if not product and row.action != "skip":
            parsed_row = PriceRow(
                line=row.line,
                title=row.title,
                price=money(row.price) if row.price is not None else None,
                stock=qty(row.stock) if row.stock is not None else None,
                barcode=row.barcode,
                unit=row.unit,
                category=row.category,
            )
            product, _score, _reason = _match_product(parsed_row, by_barcode, by_slug, by_title, titles)

        if row.action == "skip" or (row.action == "update" and not product):
            skipped += 1
            continue
        if row.action == "create" and product is None and not row.title:
            skipped += 1
            messages.append(f"Строка {row.line}: нет названия для создания товара")
            continue

        changed = False
        try:
            if product is None:
                if not payload.create_missing:
                    skipped += 1
                    continue
                if row.price is None:
                    skipped += 1
                    messages.append(f"Строка {row.line}: для нового товара нужна цена")
                    continue
                category = _find_category(db, parsed_row, payload.category_id)
                product = Product(
                    slug=_unique_slug(db, row.title),
                    barcode=None,
                    title=row.title.strip(),
                    subtitle="",
                    category_id=category.id if category else None,
                    unit=row.unit or "piece",
                    price=money(row.price),
                    discount_percent=0,
                    is_daily_deal=False,
                    is_available=True,
                    is_active=True,
                    stock=qty(row.stock) if row.stock is not None else None,
                    weight_note="",
                    image_url=None,
                    gallery=[],
                    badges=[],
                    short_description="",
                    description="",
                    origin="",
                    season="",
                    nutrition={},
                    cooking_tips="",
                    storage_tips="",
                    sort_order=100,
                )
                db.add(product)
                db.flush()
                if row.barcode:
                    try:
                        barcode_service.assign(db, product, row.barcode)
                    except HTTPException:
                        barcode_service.assign_default(db, product)
                else:
                    barcode_service.assign_default(db, product)
                created += 1
                changed = True
            else:
                if payload.update_prices and row.price is not None and money(row.price) != product.price:
                    product.price = money(row.price)
                    changed = True
                if payload.update_stock and row.stock is not None:
                    current = qty(product.stock or 0)
                    target = qty(row.stock)
                    if current != target:
                        apply_move(
                            db,
                            product,
                            kind=KIND_ADJUST,
                            quantity=float(target),
                            reason=f"Импорт прайса {payload.filename or ''}".strip(),
                            actor=actor,
                        )
                        changed = True
                if row.barcode and not product.barcode:
                    try:
                        barcode_service.assign(db, product, row.barcode)
                        changed = True
                    except HTTPException:
                        messages.append(f"Строка {row.line}: штрихкод {row.barcode} уже занят")
                if changed:
                    updated += 1
        except HTTPException as exc:
            errors += 1
            messages.append(f"Строка {row.line}: {exc.detail}")
        except (ValueError, InvalidOperation) as exc:
            errors += 1
            messages.append(f"Строка {row.line}: {exc}")

    batch = PriceImport(
        filename=payload.filename[:255],
        source=(payload.source or "text")[:16],
        total=len(payload.rows),
        updated=updated,
        created=created,
        skipped=skipped,
        errors=errors,
        actor=actor[:120],
        details={"messages": messages[:100]},
    )
    db.add(batch)
    db.flush()
    return batch


def serialize_batch(batch: PriceImport) -> dict:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "source": batch.source,
        "total": batch.total,
        "updated": batch.updated,
        "created": batch.created,
        "skipped": batch.skipped,
        "errors": batch.errors,
        "actor": batch.actor,
        "messages": (batch.details or {}).get("messages", []),
        "created_at": batch.created_at,
    }
