import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import EstadoMedia

from .base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, pg_enum


class MediaAsset(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "media_assets"

    propietario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
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
        pg_enum(EstadoMedia, "estado_media"),
        default=EstadoMedia.PENDIENTE,
        server_default=EstadoMedia.PENDIENTE.value,
    )
    # Los entregables de un pedido van a un bucket privado (lote 8)
    bucket: Mapped[str] = mapped_column(String, server_default="medios")
    # El tipo declarado al pedir la subida
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # El declarado, y despues el real al confirmar
    tamano_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Nula hasta confirmar: es lo que distingue un medio confirmado
    subido_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
