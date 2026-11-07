"""provisioning jobs and tenant hosting fields

Revision ID: b7c4a1f9d2e3
Revises: 147df87ead26
Create Date: 2026-11-07 10:40:00.000000

Хостинг и запуск сайтов: поля tenant и очередь задач с чек-листом.
Режим ручной/ассистируемый (у hoster.by нет публичного API заказа услуг).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "b7c4a1f9d2e3"
down_revision: Union[str, None] = "147df87ead26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column("hosting_provider", sa.String(length=40), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("hosting_tariff", sa.String(length=80), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("hosting_account", sa.String(length=120), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "deploy_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_started",
            )
        )
        batch.add_column(
            sa.Column("deploy_url", sa.String(length=255), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("ops_note", sa.Text(), nullable=False, server_default=""))
    op.create_index("ix_tenants_deploy_status", "tenants", ["deploy_status"])

    op.create_table(
        "provisioning_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="launch"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", UTCDateTime(timezone=True), nullable=True),
        sa.Column("completed_at", UTCDateTime(timezone=True), nullable=True),
        sa.Column("created_at", UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", UTCDateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provisioning_jobs_kind", "provisioning_jobs", ["kind"])
    op.create_index("ix_provisioning_jobs_status", "provisioning_jobs", ["status"])
    op.create_index("ix_provisioning_jobs_tenant_id", "provisioning_jobs", ["tenant_id"])
    op.create_index("ix_provisioning_jobs_created_at", "provisioning_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_provisioning_jobs_created_at", table_name="provisioning_jobs")
    op.drop_index("ix_provisioning_jobs_tenant_id", table_name="provisioning_jobs")
    op.drop_index("ix_provisioning_jobs_status", table_name="provisioning_jobs")
    op.drop_index("ix_provisioning_jobs_kind", table_name="provisioning_jobs")
    op.drop_table("provisioning_jobs")

    op.drop_index("ix_tenants_deploy_status", table_name="tenants")
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("ops_note")
        batch.drop_column("deploy_url")
        batch.drop_column("deploy_status")
        batch.drop_column("hosting_account")
        batch.drop_column("hosting_tariff")
        batch.drop_column("hosting_provider")
