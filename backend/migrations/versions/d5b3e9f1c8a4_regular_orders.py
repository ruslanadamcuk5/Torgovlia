"""regular_orders

Revision ID: d5b3e9f1c8a4
Revises: c1f5a8d3b7e2
Create Date: 2026-11-09 11:20:00.000000

Регулярные заказы: подписка покупателя, состав и дата следующего заказа.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "d5b3e9f1c8a4"
down_revision: Union[str, None] = "c1f5a8d3b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regular_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="active"),
        sa.Column("next_order_date", sa.Date(), nullable=False),
        sa.Column("last_order_id", sa.Integer(), nullable=True),
        sa.Column("last_order_at", UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("fulfillment", sa.String(length=12), nullable=False, server_default="pickup"),
        sa.Column("delivery_zone_id", sa.Integer(), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["delivery_zone_id"], ["delivery_zones.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regular_orders_tenant_id", "regular_orders", ["tenant_id"])
    op.create_index("ix_regular_orders_user_id", "regular_orders", ["user_id"])
    op.create_index("ix_regular_orders_phone", "regular_orders", ["phone"])
    op.create_index("ix_regular_orders_status", "regular_orders", ["status"])
    op.create_index("ix_regular_orders_next_order_date", "regular_orders", ["next_order_date"])
    op.create_index("ix_regular_orders_created_at", "regular_orders", ["created_at"])

    op.create_table(
        "regular_order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=12), nullable=False, server_default="piece"),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["regular_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regular_order_items_tenant_id", "regular_order_items", ["tenant_id"])
    op.create_index(
        "ix_regular_order_items_subscription_id", "regular_order_items", ["subscription_id"]
    )
    op.create_index("ix_regular_order_items_product_id", "regular_order_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_regular_order_items_product_id", table_name="regular_order_items")
    op.drop_index("ix_regular_order_items_subscription_id", table_name="regular_order_items")
    op.drop_index("ix_regular_order_items_tenant_id", table_name="regular_order_items")
    op.drop_table("regular_order_items")

    op.drop_index("ix_regular_orders_created_at", table_name="regular_orders")
    op.drop_index("ix_regular_orders_next_order_date", table_name="regular_orders")
    op.drop_index("ix_regular_orders_status", table_name="regular_orders")
    op.drop_index("ix_regular_orders_phone", table_name="regular_orders")
    op.drop_index("ix_regular_orders_user_id", table_name="regular_orders")
    op.drop_index("ix_regular_orders_tenant_id", table_name="regular_orders")
    op.drop_table("regular_orders")
