"""platform interest analytics

Revision ID: d4a7f1c9b3e6
Revises: b8d4e2c6a9f1
Create Date: 2026-11-08 21:20:00.000000

Обезличенные события интереса к платформе: визиты, демо и регистрации.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "d4a7f1c9b3e6"
down_revision: Union[str, None] = "b8d4e2c6a9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("referrer", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("campaign", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("session_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("ip_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("detail", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_events_kind", "platform_events", ["kind"])
    op.create_index("ix_platform_events_source", "platform_events", ["source"])
    op.create_index("ix_platform_events_session_key", "platform_events", ["session_key"])
    op.create_index("ix_platform_events_created_at", "platform_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_events_created_at", table_name="platform_events")
    op.drop_index("ix_platform_events_session_key", table_name="platform_events")
    op.drop_index("ix_platform_events_source", table_name="platform_events")
    op.drop_index("ix_platform_events_kind", table_name="platform_events")
    op.drop_table("platform_events")
