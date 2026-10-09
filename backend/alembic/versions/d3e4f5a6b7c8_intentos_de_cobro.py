"""intentos de cobro: arman la clave de idempotencia de cada intento

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cobros",
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_cobros_intentos_no_negativos"), "cobros", "intentos >= 0"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_cobros_intentos_no_negativos"), "cobros", type_="check")
    op.drop_column("cobros", "intentos")
