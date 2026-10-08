"""indices: sobra el simple de comentarios, falta el de busqueda de artistas

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-10-07 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# DT22: lo cubre ix_comentarios_publicacion_id_created_at
INDICE_COMENTARIOS = "ix_comentarios_publicacion_id"
INDICE_ARTISTAS = "ix_profiles_created_at_id"


def upgrade() -> None:
    op.drop_index(INDICE_COMENTARIOS, table_name="comentarios")
    op.create_index(
        INDICE_ARTISTAS,
        "profiles",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index(INDICE_ARTISTAS, table_name="profiles")
    op.create_index(INDICE_COMENTARIOS, "comentarios", ["publicacion_id"])
