import enum
import uuid
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, pg_enum


class EstadoObra(enum.StrEnum):
    EXHIBICION = "exhibicion"
    DISPONIBLE = "disponible"


class TipoServicio(enum.StrEnum):
    ENCARGO = "encargo"
    EVENTO = "evento"


class Obra(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "obras"
    __table_args__ = (
        CheckConstraint(
            "estado <> 'disponible' OR (precio IS NOT NULL AND precio > 0)",
            name="precio_si_esta_a_la_venta",
        ),
        Index(
            "ix_obras_style_embedding",
            "style_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"style_embedding": "vector_l2_ops"},
        ),
    )

    artista_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    titulo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[EstadoObra] = mapped_column(
        pg_enum(EstadoObra, "estado_obra"), default=EstadoObra.EXHIBICION
    )
    precio: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    categorias: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    style_embedding = mapped_column(Vector(1536), nullable=True)
    # Detecta la misma obra subida por cuentas distintas
    hash_imagen: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class Servicio(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "servicios"

    artista_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    titulo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str | None] = mapped_column(String, nullable=True)
    precio_base: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tipo: Mapped[TipoServicio] = mapped_column(pg_enum(TipoServicio, "tipo_servicio"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
