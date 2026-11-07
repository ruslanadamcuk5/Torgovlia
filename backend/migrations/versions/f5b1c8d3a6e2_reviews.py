"""reviews

Revision ID: f5b1c8d3a6e2
Revises: c4a9d2e7f1b8
Create Date: 2026-11-07 19:40:00.000000

Отзывы покупателей с модерацией и рейтингами товаров.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "f5b1c8d3a6e2"
down_revision: Union[str, None] = "c4a9d2e7f1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("admin_comment", sa.Text(), nullable=False),
        sa.Column("is_verified_purchase", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_tenant_id", "reviews", ["tenant_id"])
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])
    op.create_index("ix_reviews_status", "reviews", ["status"])
    op.create_index("ix_reviews_created_at", "reviews", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reviews_created_at", table_name="reviews")
    op.drop_index("ix_reviews_status", table_name="reviews")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_reviews_tenant_id", table_name="reviews")
    op.drop_table("reviews")
