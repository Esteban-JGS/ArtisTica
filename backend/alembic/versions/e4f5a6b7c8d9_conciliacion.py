"""conciliacion: ledger con clave unica y eventos de la pasarela reintentables

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONTOS_OPCIONALES = ("tarifa_artistica", "costo_procesamiento", "monto_neto_artista")
LLAVES_LEDGER = ("pedido_id", "cobro_id", "profile_id")
INDICE_PENDIENTES = "ix_eventos_pasarela_pendientes"


def upgrade() -> None:
    # La tabla esta vacia en todo entorno: nadie la escribia
    op.add_column("ledger_entries", sa.Column("clave", sa.String(), nullable=False))
    op.create_unique_constraint(
        op.f("uq_ledger_entries_clave"), "ledger_entries", ["clave"]
    )
    for columna in MONTOS_OPCIONALES:
        op.alter_column(
            "ledger_entries",
            columna,
            existing_type=sa.Numeric(12, 2),
            nullable=True,
        )
    for columna in LLAVES_LEDGER:
        op.create_index(
            op.f(f"ix_ledger_entries_{columna}"), "ledger_entries", [columna]
        )

    op.add_column(
        "eventos_pasarela", sa.Column("referencia", sa.String(), nullable=True)
    )
    op.add_column(
        "eventos_pasarela",
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        INDICE_PENDIENTES,
        "eventos_pasarela",
        ["created_at"],
        postgresql_where=sa.text("procesado_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDICE_PENDIENTES, table_name="eventos_pasarela")
    op.drop_column("eventos_pasarela", "intentos")
    op.drop_column("eventos_pasarela", "referencia")

    for columna in LLAVES_LEDGER:
        op.drop_index(op.f(f"ix_ledger_entries_{columna}"), table_name="ledger_entries")
    # Volver a NOT NULL falla si ya hay filas con nulos. Es aceptable: es una
    # vuelta atras de desarrollo
    for columna in MONTOS_OPCIONALES:
        op.alter_column(
            "ledger_entries",
            columna,
            existing_type=sa.Numeric(12, 2),
            nullable=False,
        )
    op.drop_constraint(
        op.f("uq_ledger_entries_clave"), "ledger_entries", type_="unique"
    )
    op.drop_column("ledger_entries", "clave")
