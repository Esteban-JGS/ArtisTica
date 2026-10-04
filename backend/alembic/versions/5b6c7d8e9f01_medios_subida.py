"""medios: subida firmada

Revision ID: 5b6c7d8e9f01
Revises: 1a2b3c4d5e6f
Create Date: 2026-10-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b6c7d8e9f01"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mismo nombre que da NAMING_CONVENTION ("ix_%(column_0_label)s")
INDICE_PROPIETARIO = "ix_media_assets_propietario_id"


def upgrade() -> None:
    op.add_column(
        "media_assets",
        sa.Column("bucket", sa.String(), server_default="medios", nullable=False),
    )
    op.add_column("media_assets", sa.Column("content_type", sa.String()))
    op.add_column("media_assets", sa.Column("tamano_bytes", sa.BigInteger()))
    op.add_column("media_assets", sa.Column("subido_en", sa.DateTime(timezone=True)))
    op.create_index(INDICE_PROPIETARIO, "media_assets", ["propietario_id"])


def downgrade() -> None:
    op.drop_index(INDICE_PROPIETARIO, table_name="media_assets")
    op.drop_column("media_assets", "subido_en")
    op.drop_column("media_assets", "tamano_bytes")
    op.drop_column("media_assets", "content_type")
    op.drop_column("media_assets", "bucket")
