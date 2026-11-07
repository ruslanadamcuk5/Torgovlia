"""platform global settings

Revision ID: b120fc322d8c
Revises: e25532a28420
Create Date: 2026-11-07 13:40:00.000000

Глобальные настройки платформы: бренд, контакты, лимиты, режим набора.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = "b120fc322d8c"
down_revision: Union[str, None] = "e25532a28420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("updated_at", UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
