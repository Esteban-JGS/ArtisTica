"""comentarios: respuestas de un nivel y me gusta en comentarios

Revision ID: a0b1c2d3e4f5
Revises: 9e0f1a2b3c45
Create Date: 2026-10-07 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "9e0f1a2b3c45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDICE_PUBLICACION = "ix_comentarios_publicacion_id_created_at"
INDICE_RESPUESTAS = "ix_comentarios_respuesta_a_id_created_at"
FK_RESPUESTA = "fk_comentarios_respuesta_a_id_comentarios"
ME_GUSTA = "me_gusta_comentarios"


def upgrade() -> None:
    op.add_column("comentarios", sa.Column("respuesta_a_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        FK_RESPUESTA,
        "comentarios",
        "comentarios",
        ["respuesta_a_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(INDICE_PUBLICACION, "comentarios", ["publicacion_id", "created_at"])
    op.create_index(INDICE_RESPUESTAS, "comentarios", ["respuesta_a_id", "created_at"])

    op.create_table(
        ME_GUSTA,
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("comentario_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["comentario_id"],
            ["comentarios.id"],
            name="fk_me_gusta_comentarios_comentario_id_comentarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_me_gusta_comentarios_profile_id_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_me_gusta_comentarios"),
        sa.UniqueConstraint(
            "comentario_id",
            "profile_id",
            name="uq_me_gusta_comentarios_comentario_id_profile_id",
        ),
    )
    # RLS activo y sin politicas: la app solo entra por la API
    op.execute(f"ALTER TABLE {ME_GUSTA} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.drop_table(ME_GUSTA)
    op.drop_index(INDICE_RESPUESTAS, table_name="comentarios")
    op.drop_index(INDICE_PUBLICACION, table_name="comentarios")
    op.drop_constraint(FK_RESPUESTA, "comentarios", type_="foreignkey")
    op.drop_column("comentarios", "respuesta_a_id")
