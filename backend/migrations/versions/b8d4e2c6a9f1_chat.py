"""customer chat

Revision ID: b8d4e2c6a9f1
Revises: f3c7d9a1b5e2
Create Date: 2026-11-08 20:05:00.000000

Диалоги покупателей с магазином и сообщения чата.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "b8d4e2c6a9f1"
down_revision: Union[str, None] = "f3c7d9a1b5e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=190), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="open"),
        sa.Column("unread_staff", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unread_customer", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("last_message_at", UTCDateTime(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "session_key", name="uq_chat_tenant_session"),
    )
    op.create_index("ix_chat_threads_tenant_id", "chat_threads", ["tenant_id"])
    op.create_index("ix_chat_threads_session_key", "chat_threads", ["session_key"])
    op.create_index("ix_chat_threads_phone", "chat_threads", ["phone"])
    op.create_index("ix_chat_threads_status", "chat_threads", ["status"])
    op.create_index("ix_chat_threads_last_message_at", "chat_threads", ["last_message_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("author_type", sa.String(length=12), nullable=False, server_default="customer"),
        sa.Column("author_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_tenant_id", "chat_messages", ["tenant_id"])
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_tenant_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_last_message_at", table_name="chat_threads")
    op.drop_index("ix_chat_threads_status", table_name="chat_threads")
    op.drop_index("ix_chat_threads_phone", table_name="chat_threads")
    op.drop_index("ix_chat_threads_session_key", table_name="chat_threads")
    op.drop_index("ix_chat_threads_tenant_id", table_name="chat_threads")
    op.drop_table("chat_threads")
