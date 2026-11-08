"""crm customer notes and tags

Revision ID: f3c7d9a1b5e2
Revises: e9b4c1a8f3d2
Create Date: 2026-11-08 19:10:00.000000

Заметки и метки в карточке клиента.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "f3c7d9a1b5e2"
down_revision: Union[str, None] = "e9b4c1a8f3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_notes_tenant_id", "customer_notes", ["tenant_id"])
    op.create_index("ix_customer_notes_phone", "customer_notes", ["phone"])
    op.create_index("ix_customer_notes_created_at", "customer_notes", ["created_at"])

    op.create_table(
        "customer_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("tag", sa.String(length=40), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "phone", "tag", name="uq_customer_tags_phone_tag"),
    )
    op.create_index("ix_customer_tags_tenant_id", "customer_tags", ["tenant_id"])
    op.create_index("ix_customer_tags_phone", "customer_tags", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_customer_tags_phone", table_name="customer_tags")
    op.drop_index("ix_customer_tags_tenant_id", table_name="customer_tags")
    op.drop_table("customer_tags")
    op.drop_index("ix_customer_notes_created_at", table_name="customer_notes")
    op.drop_index("ix_customer_notes_phone", table_name="customer_notes")
    op.drop_index("ix_customer_notes_tenant_id", table_name="customer_notes")
    op.drop_table("customer_notes")
