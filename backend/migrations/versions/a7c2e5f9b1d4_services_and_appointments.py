"""services, specialists and appointments

Revision ID: a7c2e5f9b1d4
Revises: d5b3e9f1c8a4
Create Date: 2026-11-13 10:00:00.000000

Универсальный слой услуг: тип бизнеса у арендатора, вид позиции каталога,
специалисты и онлайн-запись. Товарный режим сохраняется по умолчанию.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "a7c2e5f9b1d4"
down_revision: Union[str, None] = "d5b3e9f1c8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column("business_type", sa.String(length=16), nullable=False, server_default="goods")
        )
        batch.create_index("ix_tenants_business_type", ["business_type"])

    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("kind", sa.String(length=12), nullable=False, server_default="goods")
        )
        batch.add_column(
            sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_index("ix_products_kind", ["kind"])

    op.create_table(
        "specialists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=190), nullable=True),
        sa.Column("service_ids", sa.JSON(), nullable=False),
        sa.Column("working_hours", sa.JSON(), nullable=False),
        sa.Column("time_off", sa.JSON(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_specialists_tenant_slug"),
    )
    op.create_index("ix_specialists_tenant_id", "specialists", ["tenant_id"])
    op.create_index("ix_specialists_slug", "specialists", ["slug"])
    op.create_index("ix_specialists_is_active", "specialists", ["is_active"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("specialist_id", sa.Integer(), nullable=True),
        sa.Column("service_title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("specialist_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("starts_at", UTCDateTime(), nullable=False),
        sa.Column("ends_at", UTCDateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("admin_comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="site"),
        sa.Column("status_history", sa.JSON(), nullable=False),
        sa.Column("reminder_sent_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["specialist_id"], ["specialists.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="uq_appointments_tenant_number"),
    )
    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])
    op.create_index("ix_appointments_number", "appointments", ["number"])
    op.create_index("ix_appointments_phone", "appointments", ["phone"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointments_starts_at", "appointments", ["starts_at"])
    op.create_index("ix_appointments_product_id", "appointments", ["product_id"])
    op.create_index("ix_appointments_specialist_id", "appointments", ["specialist_id"])
    op.create_index("ix_appointments_created_at", "appointments", ["created_at"])


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("specialists")
    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_kind")
        batch.drop_column("capacity")
        batch.drop_column("buffer_minutes")
        batch.drop_column("duration_minutes")
        batch.drop_column("kind")
    with op.batch_alter_table("tenants") as batch:
        batch.drop_index("ix_tenants_business_type")
        batch.drop_column("business_type")
