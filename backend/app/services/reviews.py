"""Отзывы покупателей: публикация, рейтинги и модерация."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, Review, REVIEW_PUBLISHED, REVIEW_PENDING
from app.platform.sync import is_enabled
from app.security import format_phone
from app.tenancy import current_tenant


def feature_enabled(db: Session) -> bool:
    tenant = current_tenant()
    return bool(tenant and is_enabled(db, tenant.id, "reviews"))


def attach_ratings(db: Session, payloads: list[dict]) -> list[dict]:
    """Добавляет средний рейтинг и число опубликованных отзывов к товарам."""
    ids = [item["id"] for item in payloads if item.get("id")]
    if not ids:
        return payloads
    rows = db.execute(
        select(Review.product_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.product_id.in_(ids), Review.status == REVIEW_PUBLISHED)
        .group_by(Review.product_id)
    ).all()
    stats = {product_id: (round(float(average or 0), 2), int(count or 0)) for product_id, average, count in rows}
    for item in payloads:
        rating, count = stats.get(item.get("id"), (0.0, 0))
        item["rating"] = rating
        item["reviews_count"] = count
    return payloads


def summary(db: Session, product_id: int) -> dict:
    rows = db.execute(
        select(Review.rating, func.count(Review.id))
        .where(Review.product_id == product_id, Review.status == REVIEW_PUBLISHED)
        .group_by(Review.rating)
    ).all()
    distribution = {str(star): 0 for star in range(5, 0, -1)}
    total = 0
    weighted = 0
    for rating, count in rows:
        value = int(count or 0)
        total += value
        weighted += int(rating or 0) * value
        distribution[str(int(rating))] = value
    average = round(weighted / total, 2) if total else 0.0
    return {"total": total, "average": average, "distribution": distribution}


def list_published(db: Session, product_id: int, limit: int = 50) -> list[Review]:
    return list(
        db.scalars(
            select(Review)
            .where(Review.product_id == product_id, Review.status == REVIEW_PUBLISHED)
            .order_by(Review.created_at.desc())
            .limit(limit)
        ).all()
    )


def public_payload(review: Review, product: Product | None = None) -> dict:
    return {
        "id": review.id,
        "product_id": review.product_id,
        "product_title": product.title if product else "",
        "product_slug": product.slug if product else "",
        "customer_name": review.customer_name,
        "rating": int(review.rating or 0),
        "text": review.text or "",
        "status": review.status,
        "is_verified_purchase": bool(review.is_verified_purchase),
        "published_at": review.published_at,
        "created_at": review.created_at,
    }


def admin_payload(review: Review, product: Product | None = None) -> dict:
    data = public_payload(review, product)
    data.update(
        {
            "admin_comment": review.admin_comment or "",
            "phone_formatted": format_phone(review.phone) if review.phone else "",
        }
    )
    return data


def moderate(review: Review, status_value: str, comment: str = "") -> Review:
    review.status = status_value
    review.admin_comment = (comment or "").strip()
    if status_value == REVIEW_PUBLISHED:
        review.published_at = review.published_at or datetime.now(timezone.utc)
    return review


def make_review(
    *,
    product_id: int,
    customer_name: str,
    phone: str,
    rating: int,
    text: str,
    user_id: int | None = None,
    order_id: int | None = None,
    verified: bool = False,
) -> Review:
    return Review(
        product_id=product_id,
        user_id=user_id,
        order_id=order_id,
        customer_name=customer_name.strip(),
        phone=phone,
        rating=rating,
        text=text.strip(),
        status=REVIEW_PENDING,
        is_verified_purchase=verified,
    )
