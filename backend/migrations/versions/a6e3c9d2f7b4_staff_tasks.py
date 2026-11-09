"""staff tasks

Revision ID: a6e3c9d2f7b4
Revises: d4a7f1c9b3e6
Create Date: 2026-11-08 21:40:00.000000

Поручения сотрудникам: срок, приоритет, ответственный и связь с заказом.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "a6e3c9d2f7b4"
down_revision: Union[str, None] = "d4a7f1c9b3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=14), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="normal"),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_tasks_tenant_id", "staff_tasks", ["tenant_id"])
    op.create_index("ix_staff_tasks_status", "staff_tasks", ["status"])
    op.create_index("ix_staff_tasks_assignee_id", "staff_tasks", ["assignee_id"])
    op.create_index("ix_staff_tasks_order_id", "staff_tasks", ["order_id"])
    op.create_index("ix_staff_tasks_due_date", "staff_tasks", ["due_date"])
    op.create_index("ix_staff_tasks_created_at", "staff_tasks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_staff_tasks_created_at", table_name="staff_tasks")
    op.drop_index("ix_staff_tasks_due_date", table_name="staff_tasks")
    op.drop_index("ix_staff_tasks_order_id", table_name="staff_tasks")
    op.drop_index("ix_staff_tasks_assignee_id", table_name="staff_tasks")
    op.drop_index("ix_staff_tasks_status", table_name="staff_tasks")
    op.drop_index("ix_staff_tasks_tenant_id", table_name="staff_tasks")
    op.drop_table("staff_tasks")
