"""esquema: defectos en la base y moderacion en espanol

Revision ID: 7c8d9e0f1a23
Revises: 5b6c7d8e9f01
Create Date: 2026-10-04 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c8d9e0f1a23"
down_revision: str | None = "5b6c7d8e9f01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Escritas a mano: una migracion no depende de los modelos, que cambian despues.
# Con los nombres ya renombrados; el upgrade renombra antes y el downgrade despues.

# IdMixin
TABLAS_CON_ID = [
    "follows",
    "obras",
    "servicios",
    "publicaciones",
    "comentarios",
    "reacciones",
    "media_assets",
    "consultas",
    "mensajes",
    "pedidos",
    "cobros",
    "resenas",
    "entregables",
    "disputas",
    "ledger_entries",
    "eventos_pasarela",
    "post_views",
    "jobs",
    "reportes",
    "acciones_moderacion",
]

# TimestampMixin: las mismas mas profiles, cuyo id viene de auth.users
TABLAS_CON_TIEMPO = ["profiles", *TABLAS_CON_ID]

# (tabla, columna, expresion SQL)
DEFECTOS: list[tuple[str, str, str]] = [
    ("profiles", "categorias", "'{}'"),
    ("profiles", "rol", "'publico'"),
    ("profiles", "plan", "'taller'"),
    ("profiles", "is_verified", "false"),
    ("profiles", "pasarela_onboarding", "'no_iniciado'"),
    ("obras", "estado", "'exhibicion'"),
    ("obras", "categorias", "'{}'"),
    ("servicios", "activo", "true"),
    ("consultas", "estado", "'abierta'"),
    ("media_assets", "estado", "'pendiente'"),
    ("pedidos", "estado", "'cotizado'"),
    ("pedidos", "moneda", "'CRC'"),
    ("cobros", "estado", "'pendiente'"),
    ("cobros", "monto_reembolsado", "0"),
    ("disputas", "estado", "'abierta'"),
    ("jobs", "status", "'pending'"),
    ("jobs", "attempts", "0"),
    ("jobs", "max_attempts", "3"),
    ("reportes", "estado", "'pendiente'"),
]

# Cada entrada es la tabla, el nombre anterior y el nuevo
COLUMNAS_RENOMBRADAS = [
    ("reportes", "reporter_id", "reportante_id"),
    ("reportes", "target_type", "objetivo_tipo"),
    ("reportes", "target_id", "objetivo_id"),
    ("reportes", "reason", "motivo"),
    ("acciones_moderacion", "admin_id", "moderador_id"),
    ("acciones_moderacion", "target_type", "objetivo_tipo"),
    ("acciones_moderacion", "target_id", "objetivo_id"),
    ("acciones_moderacion", "action", "accion"),
]

# (tabla, columna) de persona: llave foranea a profiles e indice
PERSONAS = [
    ("reportes", "reportante_id"),
    ("acciones_moderacion", "moderador_id"),
]


def _todos_los_defectos() -> list[tuple[str, str, str]]:
    return [
        *((t, "id", "gen_random_uuid()") for t in TABLAS_CON_ID),
        *((t, "created_at", "now()") for t in TABLAS_CON_TIEMPO),
        *((t, "updated_at", "now()") for t in TABLAS_CON_TIEMPO),
        *DEFECTOS,
    ]


def upgrade() -> None:
    # 1. Moderacion en espanol. El RLS es atributo de la tabla y sobrevive al rename.
    op.rename_table("moderation_actions", "acciones_moderacion")
    op.execute(
        "ALTER TABLE acciones_moderacion "
        "RENAME CONSTRAINT pk_moderation_actions TO pk_acciones_moderacion"
    )
    for tabla, antes, despues in COLUMNAS_RENOMBRADAS:
        op.alter_column(tabla, antes, new_column_name=despues)

    for tabla, columna in PERSONAS:
        op.alter_column(tabla, columna, existing_type=sa.Uuid(), nullable=True)
        op.create_foreign_key(
            f"fk_{tabla}_{columna}_profiles",
            tabla,
            "profiles",
            [columna],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{tabla}_{columna}", tabla, [columna])

    # 2. Defectos en la base
    for tabla, columna, expresion in _todos_los_defectos():
        op.alter_column(tabla, columna, server_default=sa.text(expresion))


def downgrade() -> None:
    for tabla, columna, _ in _todos_los_defectos():
        op.alter_column(tabla, columna, server_default=None)

    # Falla si quedaron filas con la persona nula, que antes no se permitia
    for tabla, columna in PERSONAS:
        op.drop_index(f"ix_{tabla}_{columna}", table_name=tabla)
        op.drop_constraint(f"fk_{tabla}_{columna}_profiles", tabla, type_="foreignkey")
        op.alter_column(tabla, columna, existing_type=sa.Uuid(), nullable=False)

    for tabla, antes, despues in reversed(COLUMNAS_RENOMBRADAS):
        op.alter_column(tabla, despues, new_column_name=antes)
    op.execute(
        "ALTER TABLE acciones_moderacion "
        "RENAME CONSTRAINT pk_acciones_moderacion TO pk_moderation_actions"
    )
    op.rename_table("acciones_moderacion", "moderation_actions")
