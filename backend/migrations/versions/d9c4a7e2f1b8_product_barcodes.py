"""product barcodes

Revision ID: d9c4a7e2f1b8
Revises: c6e9a4b2d3f7
Create Date: 2026-11-08 13:10:00.000000

Добавляет EAN-13 товарам и заполняет коды уже созданным позициям.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9c4a7e2f1b8"
down_revision: Union[str, None] = "c6e9a4b2d3f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_digit(base: str) -> str:
    total = sum(int(char) * (3 if index % 2 else 1) for index, char in enumerate(base))
    return str((10 - total % 10) % 10)


def _barcode(product_id: int) -> str:
    base = f"20{product_id:010d}"[-12:]
    return base + _check_digit(base)


def upgrade() -> None:
    op.add_column("products", sa.Column("barcode", sa.String(length=32), nullable=True))
    op.create_index("ix_products_barcode", "products", ["barcode"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id FROM products WHERE barcode IS NULL OR barcode = ''")
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE products SET barcode = :code WHERE id = :product_id"),
            {"code": _barcode(int(row[0])), "product_id": int(row[0])},
        )


def downgrade() -> None:
    op.drop_index("ix_products_barcode", table_name="products")
    op.drop_column("products", "barcode")
