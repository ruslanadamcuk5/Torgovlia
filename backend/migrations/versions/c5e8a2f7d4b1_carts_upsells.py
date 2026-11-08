"""carts and upsell rules

Revision ID: c5e8a2f7d4b1
Revises: a7c2e9d4b1f8
Create Date: 2026-11-08 17:30:00.000000

Корзины для напоминаний и ручные рекомендации «с этим покупают».
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "c5e8a2f7d4b1"
down_revision: Union[str, None] = "a7c2e9d4b1f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reminded_at", UTCDateTime(), nullable=True),
        sa.Column("last_activity_at", UTCDateTime(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "session_key", name="uq_carts_tenant_session"),
    )
    op.create_index("ix_carts_tenant_id", "carts", ["tenant_id"])
    op.create_index("ix_carts_session_key", "carts", ["session_key"])
    op.create_index("ix_carts_phone", "carts", ["phone"])
    op.create_index("ix_carts_status", "carts", ["status"])
    op.create_index("ix_carts_last_activity_at", "carts", ["last_activity_at"])

    op.create_table(
        "upsell_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_upsell_tenant_product"),
    )
    op.create_index("ix_upsell_rules_tenant_id", "upsell_rules", ["tenant_id"])
    op.create_index("ix_upsell_rules_product_id", "upsell_rules", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_upsell_rules_product_id", table_name="upsell_rules")
    op.drop_index("ix_upsell_rules_tenant_id", table_name="upsell_rules")
    op.drop_table("upsell_rules")
    op.drop_index("ix_carts_last_activity_at", table_name="carts")
    op.drop_index("ix_carts_status", table_name="carts")
    op.drop_index("ix_carts_phone", table_name="carts")
    op.drop_index("ix_carts_session_key", table_name="carts")
    op.drop_index("ix_carts_tenant_id", table_name="carts")
    op.drop_table("carts")
