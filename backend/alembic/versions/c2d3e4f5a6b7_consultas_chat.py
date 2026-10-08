"""consultas y chat: presupuesto, fecha, marcas de lectura e indices de la bandeja

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-08 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Indices simples que reemplazan los compuestos, por tabla
INDICES_VIEJOS = (
    ("ix_mensajes_consulta_id", "mensajes", ["consulta_id"]),
    ("ix_consultas_cliente_id", "consultas", ["cliente_id"]),
    ("ix_consultas_artista_id", "consultas", ["artista_id"]),
)
INDICES_NUEVOS = (
    (
        "ix_mensajes_consulta_id_created_at",
        "mensajes",
        ["consulta_id", "created_at", "id"],
    ),
    (
        "ix_consultas_cliente_id_ultimo_mensaje_at",
        "consultas",
        ["cliente_id", "ultimo_mensaje_at", "id"],
    ),
    (
        "ix_consultas_artista_id_ultimo_mensaje_at",
        "consultas",
        ["artista_id", "ultimo_mensaje_at", "id"],
    ),
)
CHECKS = (
    ("presupuesto_positivo", "presupuesto IS NULL OR presupuesto > 0"),
    ("una_referencia", "num_nonnulls(servicio_id, obra_id) <= 1"),
)
COLUMNAS_CONSULTA = (
    "presupuesto",
    "fecha_deseada",
    "ultimo_mensaje_at",
    "leido_cliente_hasta",
    "leido_artista_hasta",
)


def upgrade() -> None:
    op.add_column("consultas", sa.Column("presupuesto", sa.Numeric(12, 2)))
    op.add_column("consultas", sa.Column("fecha_deseada", sa.Date()))
    op.add_column(
        "consultas",
        sa.Column(
            "ultimo_mensaje_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Las filas que ya existen ordenan por su creacion
    op.execute("UPDATE consultas SET ultimo_mensaje_at = created_at")
    op.add_column(
        "consultas", sa.Column("leido_cliente_hasta", sa.DateTime(timezone=True))
    )
    op.add_column(
        "consultas", sa.Column("leido_artista_hasta", sa.DateTime(timezone=True))
    )
    for nombre, condicion in CHECKS:
        op.create_check_constraint(
            op.f(f"ck_consultas_{nombre}"), "consultas", condicion
        )

    op.add_column(
        "mensajes",
        sa.Column(
            "aviso_contacto",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    for nombre, tabla, _ in INDICES_VIEJOS:
        op.drop_index(nombre, table_name=tabla)
    for nombre, tabla, columnas in INDICES_NUEVOS:
        op.create_index(nombre, tabla, columnas)


def downgrade() -> None:
    for nombre, tabla, _ in INDICES_NUEVOS:
        op.drop_index(nombre, table_name=tabla)
    for nombre, tabla, columnas in INDICES_VIEJOS:
        op.create_index(nombre, tabla, columnas)

    op.drop_column("mensajes", "aviso_contacto")
    for nombre, _ in CHECKS:
        op.drop_constraint(op.f(f"ck_consultas_{nombre}"), "consultas", type_="check")
    for columna in COLUMNAS_CONSULTA:
        op.drop_column("consultas", columna)
