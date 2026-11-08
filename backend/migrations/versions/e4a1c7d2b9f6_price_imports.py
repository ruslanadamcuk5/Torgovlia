"""price import batches

Revision ID: e4a1c7d2b9f6
Revises: d9c4a7e2f1b8
Create Date: 2026-11-08 15:20:00.000000

История импорта прайсов: файл, источник, итоги и сообщения.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "e4a1c7d2b9f6"
down_revision: Union[str, None] = "d9c4a7e2f1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="csv"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actor", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_imports_tenant_id", "price_imports", ["tenant_id"])
    op.create_index("ix_price_imports_created_at", "price_imports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_price_imports_created_at", table_name="price_imports")
    op.drop_index("ix_price_imports_tenant_id", table_name="price_imports")
    op.drop_table("price_imports")
