"""Ручные рекомендации «с этим покупают»."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, UpsellRule
from app.tenancy import current_tenant, tenant_get


def rule_for(db: Session, product_id: int) -> UpsellRule | None:
    return db.scalar(
        select(UpsellRule).where(
            UpsellRule.product_id == product_id,
            UpsellRule.is_active.is_(True),
        )
    )


def related(db: Session, product: Product, fallback_limit: int = 4) -> list[Product]:
    """Сначала ручные рекомендации, затем добор из той же категории."""
    result: list[Product] = []
    rule = rule_for(db, product.id)
    if rule:
        wanted = [int(item) for item in (rule.items or []) if isinstance(item, (int, float, str))]
        if wanted:
            rows = db.scalars(
                select(Product).where(
                    Product.id.in_(wanted),
                    Product.is_active.is_(True),
                    Product.id != product.id,
                )
            ).all()
            by_id = {row.id: row for row in rows}
            for item_id in wanted:
                candidate = by_id.get(int(item_id))
                if candidate and candidate not in result:
                    result.append(candidate)
    if len(result) >= fallback_limit:
        return result[:fallback_limit]

    excluded = {product.id, *(row.id for row in result)}
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True), Product.id.notin_(excluded))
        .order_by((Product.category_id == product.category_id).desc(), Product.sort_order.asc())
        .limit(fallback_limit - len(result))
    )
    for row in db.scalars(stmt).all():
        if len(result) >= fallback_limit:
            break
        result.append(row)
    return result


def serialize(db: Session, rule: UpsellRule) -> dict:
    product = tenant_get(db, Product, rule.product_id)
    items = []
    for item_id in rule.items or []:
        candidate = tenant_get(db, Product, int(item_id)) if str(item_id).isdigit() else None
        if candidate:
            items.append(
                {
                    "id": candidate.id,
                    "title": candidate.title,
                    "slug": candidate.slug,
                    "price": float(candidate.price or 0),
                    "image_url": candidate.image_url or "",
                }
            )
    return {
        "id": rule.id,
        "product_id": rule.product_id,
        "product_title": product.title if product else "Товар удалён",
        "product_slug": product.slug if product else "",
        "items": items,
        "is_active": rule.is_active,
        "updated_at": rule.updated_at,
    }


def list_rules(db: Session) -> list[dict]:
    rows = db.scalars(select(UpsellRule).order_by(UpsellRule.updated_at.desc())).all()
    return [serialize(db, row) for row in rows]


def _clean_items(db: Session, product_id: int, items: list[int]) -> list[int]:
    cleaned: list[int] = []
    for item_id in items:
        if item_id == product_id or item_id in cleaned:
            continue
        if tenant_get(db, Product, item_id):
            cleaned.append(item_id)
        if len(cleaned) >= 8:
            break
    return cleaned


def save(db: Session, product_id: int, items: list[int], is_active: bool = True) -> UpsellRule:
    product = tenant_get(db, Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    cleaned = _clean_items(db, product_id, items)
    rule = db.scalar(select(UpsellRule).where(UpsellRule.product_id == product_id))
    if rule is None:
        rule = UpsellRule(product_id=product_id, items=cleaned, is_active=is_active)
        db.add(rule)
    else:
        rule.items = cleaned
        rule.is_active = is_active
    db.flush()
    return rule


def delete(db: Session, product_id: int) -> None:
    rule = db.scalar(select(UpsellRule).where(UpsellRule.product_id == product_id))
    if rule:
        db.delete(rule)
