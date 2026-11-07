"""platform two factor auth

Revision ID: 5256547a6427
Revises: b120fc322d8c
Create Date: 2026-11-07 14:05:00.000000

Двухфакторный вход сотрудников платформы: TOTP и резервные коды.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5256547a6427"
down_revision: Union[str, None] = "b120fc322d8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("platform_users") as batch:
        batch.add_column(sa.Column("totp_secret", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("totp_recovery_hashes", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("platform_users") as batch:
        batch.drop_column("totp_recovery_hashes")
        batch.drop_column("totp_enabled")
        batch.drop_column("totp_secret")
