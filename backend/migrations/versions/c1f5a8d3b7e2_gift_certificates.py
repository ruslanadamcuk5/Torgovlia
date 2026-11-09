"""gift certificates

Revision ID: c1f5a8d3b7e2
Revises: a6e3c9d2f7b4
Create Date: 2026-11-09 09:30:00.000000

Подарочные сертификаты: выпуск, баланс, история и оплата заказа.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "c1f5a8d3b7e2"
down_revision: Union[str, None] = "a6e3c9d2f7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gift_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("initial_amount", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("balance", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("recipient_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("recipient_email", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("sender_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("sender_phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("issued_by_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", UTCDateTime(), nullable=True),
        sa.Column("activated_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_gift_certificates_tenant_code"),
    )
    op.create_index("ix_gift_certificates_tenant_id", "gift_certificates", ["tenant_id"])
    op.create_index("ix_gift_certificates_code", "gift_certificates", ["code"])
    op.create_index("ix_gift_certificates_status", "gift_certificates", ["status"])
    op.create_index("ix_gift_certificates_expires_at", "gift_certificates", ["expires_at"])
    op.create_index("ix_gift_certificates_created_at", "gift_certificates", ["created_at"])

    op.create_table(
        "gift_certificate_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("certificate_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=12), nullable=False, server_default="issue"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("balance_after", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("actor", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["certificate_id"], ["gift_certificates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gift_certificate_transactions_tenant_id",
        "gift_certificate_transactions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_gift_certificate_transactions_certificate_id",
        "gift_certificate_transactions",
        ["certificate_id"],
    )
    op.create_index(
        "ix_gift_certificate_transactions_order_id",
        "gift_certificate_transactions",
        ["order_id"],
    )
    op.create_index(
        "ix_gift_certificate_transactions_created_at",
        "gift_certificate_transactions",
        ["created_at"],
    )

    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column(
                "gift_certificate_code", sa.String(length=24), nullable=False, server_default=""
            )
        )
        batch.add_column(
            sa.Column(
                "gift_certificate_amount",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0.00",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("gift_certificate_amount")
        batch.drop_column("gift_certificate_code")

    op.drop_index(
        "ix_gift_certificate_transactions_created_at",
        table_name="gift_certificate_transactions",
    )
    op.drop_index(
        "ix_gift_certificate_transactions_order_id",
        table_name="gift_certificate_transactions",
    )
    op.drop_index(
        "ix_gift_certificate_transactions_certificate_id",
        table_name="gift_certificate_transactions",
    )
    op.drop_index(
        "ix_gift_certificate_transactions_tenant_id",
        table_name="gift_certificate_transactions",
    )
    op.drop_table("gift_certificate_transactions")

    op.drop_index("ix_gift_certificates_created_at", table_name="gift_certificates")
    op.drop_index("ix_gift_certificates_expires_at", table_name="gift_certificates")
    op.drop_index("ix_gift_certificates_status", table_name="gift_certificates")
    op.drop_index("ix_gift_certificates_code", table_name="gift_certificates")
    op.drop_index("ix_gift_certificates_tenant_id", table_name="gift_certificates")
    op.drop_table("gift_certificates")
