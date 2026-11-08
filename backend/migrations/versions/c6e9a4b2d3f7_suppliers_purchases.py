"""suppliers and purchase orders

Revision ID: c6e9a4b2d3f7
Revises: b8f4c1d6e2a9
Create Date: 2026-11-08 11:40:00.000000

Поставщики, закупки и строки закупок.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "c6e9a4b2d3f7"
down_revision: Union[str, None] = "b8f4c1d6e2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("contact_person", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("address", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suppliers_tenant_id", "suppliers", ["tenant_id"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=24), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("supplier_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("received_at", UTCDateTime(), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_purchase_orders_tenant_number"),
    )
    op.create_index("ix_purchase_orders_tenant_id", "purchase_orders", ["tenant_id"])
    op.create_index("ix_purchase_orders_number", "purchase_orders", ["number"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])
    op.create_index("ix_purchase_orders_created_at", "purchase_orders", ["created_at"])

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=10), nullable=False, server_default="piece"),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_items_tenant_id", "purchase_items", ["tenant_id"])
    op.create_index("ix_purchase_items_purchase_id", "purchase_items", ["purchase_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_items_purchase_id", table_name="purchase_items")
    op.drop_index("ix_purchase_items_tenant_id", table_name="purchase_items")
    op.drop_table("purchase_items")
    op.drop_index("ix_purchase_orders_created_at", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_number", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_tenant_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_index("ix_suppliers_tenant_id", table_name="suppliers")
    op.drop_table("suppliers")
