"""incidents and status page

Revision ID: e25532a28420
Revises: c2f8e6a1d4b7
Create Date: 2026-11-07 13:10:00.000000

Инциденты платформы и магазинов, хронология и статус-страница.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "e25532a28420"
down_revision: Union[str, None] = "c2f8e6a1d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="minor"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="investigating"),
        sa.Column("created_by", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("started_at", UTCDateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", UTCDateTime(timezone=True), nullable=True),
        sa.Column("created_at", UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_tenant_id", "incidents", ["tenant_id"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_started_at", "incidents", ["started_at"])

    op.create_table(
        "incident_updates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="investigating"),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("author", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_updates_incident_id", "incident_updates", ["incident_id"])
    op.create_index("ix_incident_updates_created_at", "incident_updates", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_incident_updates_created_at", table_name="incident_updates")
    op.drop_index("ix_incident_updates_incident_id", table_name="incident_updates")
    op.drop_table("incident_updates")
    op.drop_index("ix_incidents_started_at", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_tenant_id", table_name="incidents")
    op.drop_table("incidents")
