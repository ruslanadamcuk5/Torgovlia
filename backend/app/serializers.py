"""Преобразование ORM-моделей в ответы API."""

from app.models import Order, Product
from app.security import format_phone
from app.utils import as_float, money


def product_payload(product: Product, include_article: bool = False) -> dict:
    price = money(product.price or 0)
    discount = max(0, min(95, int(product.discount_percent or 0)))
    final = money(price * (100 - discount) / 100)
    stock = as_float(product.stock)
    can_order = bool(product.is_active and product.is_available and (stock is None or stock > 0))
    data = {
        "id": product.id,
        "slug": product.slug,
        "title": product.title,
        "subtitle": product.subtitle or "",
        "category_id": product.category_id,
        "category_title": product.category.title if product.category else None,
        "category_slug": product.category.slug if product.category else None,
        "unit": product.unit,
        "kind": product.kind or "goods",
        "duration_minutes": int(product.duration_minutes or 0),
        "buffer_minutes": int(product.buffer_minutes or 0),
        "capacity": int(product.capacity or 1),
        "price": float(price),
        "final_price": float(final),
        "discount_percent": discount,
        "is_daily_deal": bool(product.is_daily_deal),
        "is_available": bool(product.is_available),
        "is_active": bool(product.is_active),
        "stock": stock,
        "weight_note": product.weight_note or "",
        "barcode": product.barcode,
        "image_url": product.image_url,
        "gallery": product.gallery or [],
        "badges": product.badges or [],
        "short_description": product.short_description or "",
        "description": (product.description or "") if include_article else "",
        "origin": product.origin or "",
        "season": product.season or "",
        "nutrition": product.nutrition or {},
        "cooking_tips": (product.cooking_tips or "") if include_article else "",
        "storage_tips": (product.storage_tips or "") if include_article else "",
        "sort_order": product.sort_order,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "can_order": can_order,
    }
    return data


def product_admin_payload(product: Product) -> dict:
    data = product_payload(product, include_article=True)
    data["short_description"] = product.short_description or ""
    return data


def specialist_payload(specialist, services: list[dict] | None = None) -> dict:
    return {
        "id": specialist.id,
        "slug": specialist.slug,
        "name": specialist.name,
        "role": specialist.role or "",
        "bio": specialist.bio or "",
        "photo_url": specialist.photo_url,
        "phone": specialist.phone or "",
        "email": specialist.email,
        "service_ids": list(specialist.service_ids or []),
        "services": services or [],
        "working_hours": specialist.working_hours or [],
        "time_off": specialist.time_off or [],
        "color": specialist.color or "",
        "sort_order": specialist.sort_order,
        "is_active": bool(specialist.is_active),
        "created_at": specialist.created_at,
        "updated_at": specialist.updated_at,
    }


def appointment_payload(appointment) -> dict:
    return {
        "id": appointment.id,
        "number": appointment.number,
        "product_id": appointment.product_id,
        "specialist_id": appointment.specialist_id,
        "service_title": appointment.service_title or "",
        "specialist_name": appointment.specialist_name or "",
        "customer_name": appointment.customer_name,
        "phone": appointment.phone,
        "phone_formatted": format_phone(appointment.phone),
        "email": appointment.email or "",
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "duration_minutes": int(appointment.duration_minutes or 0),
        "buffer_minutes": int(appointment.buffer_minutes or 0),
        "price": float(appointment.price or 0),
        "status": appointment.status,
        "comment": appointment.comment or "",
        "admin_comment": appointment.admin_comment or "",
        "source": appointment.source or "site",
        "status_history": appointment.status_history or [],
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
    }


def order_payload(order: Order) -> dict:
    return {
        "id": order.id,
        "number": order.number,
        "user_id": order.user_id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "phone_formatted": format_phone(order.phone),
        "pickup_date": order.pickup_date,
        "pickup_time": order.pickup_time,
        "status": order.status,
        "comment": order.comment or "",
        "admin_comment": order.admin_comment or "",
        "total_amount": float(order.total_amount or 0),
        "discount_amount": float(order.discount_amount or 0),
        "points_used": int(order.points_used or 0),
        "points_discount": float(order.points_discount or 0),
        "points_earned": int(order.points_earned or 0),
        "promo_code": order.promo_code or "",
        "gift_certificate_code": order.gift_certificate_code or "",
        "gift_certificate_amount": float(order.gift_certificate_amount or 0),
        "fulfillment": order.fulfillment or "pickup",
        "delivery_zone_name": order.delivery_zone_name or "",
        "delivery_address": order.delivery_address or "",
        "delivery_fee": float(order.delivery_fee or 0),
        "items_count": order.items_count,
        "source": order.source,
        "status_history": order.status_history or [],
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "title": item.title,
                "image_url": item.image_url,
                "unit": item.unit,
                "price": float(item.price),
                "quantity": float(item.quantity),
                "line_total": float(item.line_total),
            }
            for item in order.items
        ],
    }
