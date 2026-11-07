"""promo codes

Revision ID: c4a9d2e7f1b8
Revises: 8d1a6f4c7b90
Create Date: 2026-11-07 18:20:00.000000

Промокоды магазина и скидка в заказе.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "c4a9d2e7f1b8"
down_revision: Union[str, None] = "8d1a6f4c7b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False, server_default="percent"),
        sa.Column("value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("min_order", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", UTCDateTime(), nullable=True),
        sa.Column("ends_at", UTCDateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_promo_codes_tenant_code"),
    )
    op.create_index("ix_promo_codes_tenant_id", "promo_codes", ["tenant_id"])
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"])

    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("promo_code", sa.String(length=32), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("promo_code")
        batch.drop_column("discount_amount")

    op.drop_index("ix_promo_codes_code", table_name="promo_codes")
    op.drop_index("ix_promo_codes_tenant_id", table_name="promo_codes")
    op.drop_table("promo_codes")
