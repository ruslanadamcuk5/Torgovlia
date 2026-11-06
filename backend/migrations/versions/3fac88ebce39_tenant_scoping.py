"""tenant scoping

Revision ID: 3fac88ebce39
Revises: 3364f1a25d26
Create Date: 2026-11-06 21:50:54.306739

Добавляет tenant_id в бизнес-таблицы. Для существующей базы создаёт арендатора
по умолчанию и привязывает к нему все старые данные.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3fac88ebce39'
down_revision: Union[str, None] = '3364f1a25d26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ("categories", "products", "orders", "order_items", "audit_log")


def _default_tenant_id(bind) -> int:
    row = bind.execute(sa.text("SELECT id FROM tenants ORDER BY id LIMIT 1")).first()
    if row:
        return int(row[0])
    bind.execute(
        sa.text(
            """
            INSERT INTO tenants
                (slug, name, status, plan_code, category_preset, locale, currency,
                 timezone, is_demo, created_at, updated_at)
            VALUES
                ('rybnaya', 'Рыбная лавка', 'active', 'start', 'fish', 'ru', 'BYN',
                 'Europe/Minsk', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
    )
    return int(bind.execute(sa.text("SELECT id FROM tenants ORDER BY id LIMIT 1")).scalar_one())


def upgrade() -> None:
    bind = op.get_bind()
    tenant_id = _default_tenant_id(bind)

    # Настройки арендатора: переносим старые site_settings, если они есть.
    bind.execute(
        sa.text(
            """
            INSERT INTO tenant_settings (tenant_id, data, updated_at)
            SELECT :tid,
                   COALESCE((SELECT data FROM site_settings WHERE id = 1), '{}'),
                   CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM tenant_settings WHERE tenant_id = :tid)
            """
        ),
        {"tid": tenant_id},
    )

    # 1. Добавляем nullable-колонки, чтобы не сломать существующие строки.
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))

    # 2. Привязываем старые данные к арендатору по умолчанию.
    for table in TABLES:
        bind.execute(
            sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"),
            {"tid": tenant_id},
        )

    # 3. Делаем колонки обязательными и добавляем индексы/ограничения.
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f("ix_categories_slug"))
        batch_op.create_index(batch_op.f("ix_categories_slug"), ["slug"], unique=False)
        batch_op.create_index(batch_op.f("ix_categories_tenant_id"), ["tenant_id"], unique=False)
        batch_op.create_unique_constraint("uq_categories_tenant_slug", ["tenant_id", "slug"])
        batch_op.create_foreign_key(
            "fk_categories_tenant", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f("ix_products_slug"))
        batch_op.create_index(batch_op.f("ix_products_slug"), ["slug"], unique=False)
        batch_op.create_index(batch_op.f("ix_products_tenant_id"), ["tenant_id"], unique=False)
        batch_op.create_unique_constraint("uq_products_tenant_slug", ["tenant_id", "slug"])
        batch_op.create_foreign_key(
            "fk_products_tenant", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index(batch_op.f("ix_orders_number"))
        batch_op.create_index(batch_op.f("ix_orders_number"), ["number"], unique=False)
        batch_op.create_index(batch_op.f("ix_orders_tenant_id"), ["tenant_id"], unique=False)
        batch_op.create_unique_constraint("uq_orders_tenant_number", ["tenant_id", "number"])
        batch_op.create_foreign_key(
            "fk_orders_tenant", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f("ix_order_items_tenant_id"), ["tenant_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_order_items_tenant", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_log_tenant_id"), ["tenant_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_audit_log_tenant", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_constraint("fk_audit_log_tenant", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_audit_log_tenant_id"))
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_order_items_tenant", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_order_items_tenant_id"))
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_constraint("fk_orders_tenant", type_="foreignkey")
        batch_op.drop_constraint("uq_orders_tenant_number", type_="unique")
        batch_op.drop_index(batch_op.f("ix_orders_tenant_id"))
        batch_op.drop_index(batch_op.f("ix_orders_number"))
        batch_op.create_index(batch_op.f("ix_orders_number"), ["number"], unique=True)
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint("fk_products_tenant", type_="foreignkey")
        batch_op.drop_constraint("uq_products_tenant_slug", type_="unique")
        batch_op.drop_index(batch_op.f("ix_products_tenant_id"))
        batch_op.drop_index(batch_op.f("ix_products_slug"))
        batch_op.create_index(batch_op.f("ix_products_slug"), ["slug"], unique=True)
        batch_op.drop_column("tenant_id")

    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_constraint("fk_categories_tenant", type_="foreignkey")
        batch_op.drop_constraint("uq_categories_tenant_slug", type_="unique")
        batch_op.drop_index(batch_op.f("ix_categories_tenant_id"))
        batch_op.drop_index(batch_op.f("ix_categories_slug"))
        batch_op.create_index(batch_op.f("ix_categories_slug"), ["slug"], unique=True)
        batch_op.drop_column("tenant_id")
