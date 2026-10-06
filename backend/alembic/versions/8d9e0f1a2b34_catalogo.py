"""catalogo: orden de los medios de una obra e indice de la galeria

Revision ID: 8d9e0f1a2b34
Revises: 7c8d9e0f1a23
Create Date: 2026-10-06 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d9e0f1a2b34"
down_revision: str | None = "7c8d9e0f1a23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDICE_GALERIA = "ix_obras_artista_id_created_at"


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("orden", sa.SmallInteger(), nullable=True))
    op.create_index(
        INDICE_GALERIA,
        "obras",
        ["artista_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(INDICE_GALERIA, table_name="obras")
    op.drop_column("media_assets", "orden")
