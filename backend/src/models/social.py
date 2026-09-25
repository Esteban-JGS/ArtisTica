import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Publicacion(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "publicaciones"
    __table_args__ = (
        Index(
            "ix_publicaciones_search_vector", "search_vector", postgresql_using="gin"
        ),
    )

    artista_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    texto: Mapped[str] = mapped_column(String)
    # Una publicacion puede mostrar una obra
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("obras.id", ondelete="SET NULL"), nullable=True
    )
    search_vector = mapped_column(TSVECTOR, nullable=True)


class Comentario(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "comentarios"

    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    texto: Mapped[str] = mapped_column(String)


class Reaccion(Base, IdMixin, TimestampMixin):
    __tablename__ = "reacciones"
    __table_args__ = (UniqueConstraint("publicacion_id", "profile_id", "tipo"),)

    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    tipo: Mapped[str] = mapped_column(String)
