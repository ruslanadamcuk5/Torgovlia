"""tenant users and platform users

Revision ID: 59de200ba9a4
Revises: 962530770cc4
Create Date: 2026-11-06 22:04:28.145008

Разделяет контуры пользователей:
- users — покупатели и сотрудники конкретного магазина, уникальность телефона
  в пределах арендатора;
- platform_users — сотрудники центральной панели платформы.

Старые пользователи привязываются к арендатору по умолчанию.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db import UTCDateTime


revision: str = '59de200ba9a4'
down_revision: Union[str, None] = '962530770cc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _default_tenant_id(bind) -> int | None:
    row = bind.execute(sa.text("SELECT id FROM tenants ORDER BY id LIMIT 1")).first()
    return int(row[0]) if row else None


def upgrade() -> None:
    op.create_table(
        'platform_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=190), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_phone_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', UTCDateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', UTCDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('platform_users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_platform_users_phone'), ['phone'], unique=True)
        batch_op.create_index(batch_op.f('ix_platform_users_role'), ['role'], unique=False)

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.add_column(sa.Column('platform_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_audit_log_platform_user',
            'platform_users',
            ['platform_user_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 1. tenant_id добавляем nullable, чтобы не сломать существующие строки.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=True))

    bind = op.get_bind()
    tenant_id = _default_tenant_id(bind)
    if tenant_id is not None:
        bind.execute(
            sa.text("UPDATE users SET tenant_id = :tid WHERE tenant_id IS NULL"),
            {"tid": tenant_id},
        )

    # 2. Только после backfill колонка становится обязательной.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('tenant_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f('ix_users_phone'))
        batch_op.create_index(batch_op.f('ix_users_phone'), ['phone'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_unique_constraint('uq_users_tenant_phone', ['tenant_id', 'phone'])
        batch_op.create_foreign_key(
            'fk_users_tenant', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE'
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_tenant', type_='foreignkey')
        batch_op.drop_constraint('uq_users_tenant_phone', type_='unique')
        batch_op.drop_index(batch_op.f('ix_users_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_users_phone'))
        batch_op.create_index(batch_op.f('ix_users_phone'), ['phone'], unique=True)
        batch_op.drop_column('tenant_id')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_audit_log_platform_user', type_='foreignkey')
        batch_op.drop_column('platform_user_id')

    with op.batch_alter_table('platform_users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_platform_users_role'))
        batch_op.drop_index(batch_op.f('ix_platform_users_phone'))

    op.drop_table('platform_users')
