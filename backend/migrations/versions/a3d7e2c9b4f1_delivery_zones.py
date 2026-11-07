"""delivery zones

Revision ID: a3d7e2c9b4f1
Revises: f5b1c8d3a6e2
Create Date: 2026-11-07 21:10:00.000000

Зоны доставки и параметры доставки в заказе.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "a3d7e2c9b4f1"
down_revision: Union[str, None] = "f5b1c8d3a6e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "delivery_zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("areas", sa.Text(), nullable=False, server_default=""),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("min_order", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("free_from", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("eta", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_zones_tenant_id", "delivery_zones", ["tenant_id"])

    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column("fulfillment", sa.String(length=12), nullable=False, server_default="pickup")
        )
        batch.add_column(sa.Column("delivery_zone_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("delivery_zone_name", sa.String(length=80), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("delivery_address", sa.Text(), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0")
        )
        batch.create_foreign_key(
            "fk_orders_delivery_zone_id",
            "delivery_zones",
            ["delivery_zone_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_delivery_zone_id", type_="foreignkey")
        batch.drop_column("delivery_fee")
        batch.drop_column("delivery_address")
        batch.drop_column("delivery_zone_name")
        batch.drop_column("delivery_zone_id")
        batch.drop_column("fulfillment")

    op.drop_index("ix_delivery_zones_tenant_id", table_name="delivery_zones")
    op.drop_table("delivery_zones")
