"""feed: indices de Explorar, del filtro por categorias y de los medios

Revision ID: 9e0f1a2b3c45
Revises: 8d9e0f1a2b34
Create Date: 2026-10-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e0f1a2b3c45"
down_revision: str | None = "8d9e0f1a2b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDICE_EXPLORAR = "ix_publicaciones_created_at_id"
INDICE_CATEGORIAS = "ix_profiles_categorias"
INDICE_MEDIOS_OBRA = "ix_media_assets_obra_id"
INDICE_MEDIOS_PUBLICACION = "ix_media_assets_publicacion_id"


def upgrade() -> None:
    op.create_index(
        INDICE_EXPLORAR,
        "publicaciones",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        INDICE_CATEGORIAS, "profiles", ["categorias"], postgresql_using="gin"
    )
    op.create_index(INDICE_MEDIOS_OBRA, "media_assets", ["obra_id"])
    op.create_index(INDICE_MEDIOS_PUBLICACION, "media_assets", ["publicacion_id"])


def downgrade() -> None:
    op.drop_index(INDICE_MEDIOS_PUBLICACION, table_name="media_assets")
    op.drop_index(INDICE_MEDIOS_OBRA, table_name="media_assets")
    op.drop_index(INDICE_CATEGORIAS, table_name="profiles")
    op.drop_index(INDICE_EXPLORAR, table_name="publicaciones")
