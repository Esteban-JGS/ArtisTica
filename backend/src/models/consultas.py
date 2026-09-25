import enum
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin, pg_enum


class EstadoConsulta(enum.StrEnum):
    ABIERTA = "abierta"
    COTIZADA = "cotizada"
    CONVERTIDA = "convertida"
    DESCARTADA = "descartada"


class Consulta(Base, IdMixin, TimestampMixin):
    """Conversacion previa a un pedido. Se conserva aunque no se convierta."""

    __tablename__ = "consultas"
    __table_args__ = (
        CheckConstraint("cliente_id <> artista_id", name="cliente_no_es_artista"),
    )

    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    artista_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    servicio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("servicios.id"), nullable=True
    )
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("obras.id"), nullable=True
    )
    estado: Mapped[EstadoConsulta] = mapped_column(
        pg_enum(EstadoConsulta, "estado_consulta"), default=EstadoConsulta.ABIERTA
    )


class Mensaje(Base, IdMixin, TimestampMixin):
    """Unico mecanismo de chat del sistema."""

    __tablename__ = "mensajes"

    consulta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultas.id"), index=True
    )
    remitente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    texto: Mapped[str] = mapped_column(String)
