"""uptime checks

Revision ID: 8d1a6f4c7b90
Revises: 5256547a6427
Create Date: 2026-11-07 15:10:00.000000

История проверок доступности витрин: статус, код ответа и задержка.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "8d1a6f4c7b90"
down_revision: Union[str, None] = "5256547a6427"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uptime_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("checked_at", UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uptime_checks_tenant_id", "uptime_checks", ["tenant_id"])
    op.create_index("ix_uptime_checks_ok", "uptime_checks", ["ok"])
    op.create_index("ix_uptime_checks_checked_at", "uptime_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_uptime_checks_checked_at", table_name="uptime_checks")
    op.drop_index("ix_uptime_checks_ok", table_name="uptime_checks")
    op.drop_index("ix_uptime_checks_tenant_id", table_name="uptime_checks")
    op.drop_table("uptime_checks")
