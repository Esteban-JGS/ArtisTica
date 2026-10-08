import uuid

from sqlalchemy import Computed, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Publicacion(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "publicaciones"
    __table_args__ = (
        Index(
            "ix_publicaciones_search_vector", "search_vector", postgresql_using="gin"
        ),
        # Acceso del feed cronologico
        Index(
            "ix_publicaciones_artista_id_created_at",
            "artista_id",
            text("created_at DESC"),
        ),
        # Explorar: todas las publicaciones en el orden de la paginacion
        Index(
            "ix_publicaciones_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
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
    # Columna generada: la mantiene PostgreSQL y SQLAlchemy nunca la escribe
    search_vector = mapped_column(
        TSVECTOR, Computed("to_tsvector('spanish', texto)", persisted=True)
    )


class Comentario(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "comentarios"
    __table_args__ = (
        # Los comentarios de una publicacion, del mas viejo al mas nuevo
        Index(
            "ix_comentarios_publicacion_id_created_at", "publicacion_id", "created_at"
        ),
        # Las respuestas de un comentario, en el mismo orden
        Index(
            "ix_comentarios_respuesta_a_id_created_at", "respuesta_a_id", "created_at"
        ),
    )

    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    texto: Mapped[str] = mapped_column(String)
    # Nulo en un comentario de primer nivel. Hay un solo nivel de respuestas
    respuesta_a_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comentarios.id", ondelete="CASCADE"), nullable=True
    )


class MeGustaComentario(Base, IdMixin, TimestampMixin):
    __tablename__ = "me_gusta_comentarios"
    __table_args__ = (UniqueConstraint("comentario_id", "profile_id"),)

    comentario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comentarios.id", ondelete="CASCADE")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )


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
