"""loyalty program

Revision ID: e9b4c1a8f3d2
Revises: c5e8a2f7d4b1
Create Date: 2026-11-08 18:20:00.000000

Бонусные счета, история баллов и поля списания в заказах.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "e9b4c1a8f3d2"
down_revision: Union[str, None] = "c5e8a2f7d4b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loyalty_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("earn_per_byn", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("point_value", sa.Numeric(8, 4), nullable=False, server_default="0.0100"),
        sa.Column("max_redeem_percent", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("min_redeem_points", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_loyalty_settings_tenant"),
    )
    op.create_index("ix_loyalty_settings_tenant_id", "loyalty_settings", ["tenant_id"])

    op.create_table(
        "loyalty_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("earned_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spent_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="bronze"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_loyalty_tenant_phone"),
    )
    op.create_index("ix_loyalty_accounts_tenant_id", "loyalty_accounts", ["tenant_id"])
    op.create_index("ix_loyalty_accounts_phone", "loyalty_accounts", ["phone"])

    op.create_table(
        "loyalty_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="earn"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("actor", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["loyalty_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loyalty_transactions_tenant_id", "loyalty_transactions", ["tenant_id"])
    op.create_index("ix_loyalty_transactions_account_id", "loyalty_transactions", ["account_id"])
    op.create_index("ix_loyalty_transactions_kind", "loyalty_transactions", ["kind"])
    op.create_index("ix_loyalty_transactions_created_at", "loyalty_transactions", ["created_at"])

    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("points_used", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("points_discount", sa.Numeric(10, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("points_earned")
        batch.drop_column("points_discount")
        batch.drop_column("points_used")

    op.drop_index("ix_loyalty_transactions_created_at", table_name="loyalty_transactions")
    op.drop_index("ix_loyalty_transactions_kind", table_name="loyalty_transactions")
    op.drop_index("ix_loyalty_transactions_account_id", table_name="loyalty_transactions")
    op.drop_index("ix_loyalty_transactions_tenant_id", table_name="loyalty_transactions")
    op.drop_table("loyalty_transactions")
    op.drop_index("ix_loyalty_accounts_phone", table_name="loyalty_accounts")
    op.drop_index("ix_loyalty_accounts_tenant_id", table_name="loyalty_accounts")
    op.drop_table("loyalty_accounts")
    op.drop_index("ix_loyalty_settings_tenant_id", table_name="loyalty_settings")
    op.drop_table("loyalty_settings")
