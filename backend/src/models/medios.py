import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, pg_enum


class EstadoMedia(enum.StrEnum):
    PENDIENTE = "pendiente"
    PROCESADO = "procesado"
    FALLIDO = "fallido"


class MediaAsset(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "media_assets"

    propietario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("obras.id", ondelete="CASCADE"), nullable=True
    )
    publicacion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[EstadoMedia] = mapped_column(
        pg_enum(EstadoMedia, "estado_media"), default=EstadoMedia.PENDIENTE
    )
