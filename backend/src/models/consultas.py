import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import EstadoConsulta

from .base import Base, IdMixin, TimestampMixin, pg_enum


class Consulta(Base, IdMixin, TimestampMixin):
    """Conversacion previa a un pedido. Se conserva aunque no se convierta."""

    __tablename__ = "consultas"
    __table_args__ = (
        CheckConstraint("cliente_id <> artista_id", name="cliente_no_es_artista"),
        CheckConstraint(
            "presupuesto IS NULL OR presupuesto > 0", name="presupuesto_positivo"
        ),
        # Sobre un servicio, sobre una obra, o en general
        CheckConstraint(
            "num_nonnulls(servicio_id, obra_id) <= 1", name="una_referencia"
        ),
        # La bandeja de cada lado, por ultimo mensaje. Postgres la recorre al reves
        Index(
            "ix_consultas_cliente_id_ultimo_mensaje_at",
            "cliente_id",
            "ultimo_mensaje_at",
            "id",
        ),
        Index(
            "ix_consultas_artista_id_ultimo_mensaje_at",
            "artista_id",
            "ultimo_mensaje_at",
            "id",
        ),
    )

    # Sin indice propio: los cubren los de la bandeja
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    artista_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    servicio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("servicios.id"), nullable=True
    )
    obra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("obras.id"), nullable=True
    )
    estado: Mapped[EstadoConsulta] = mapped_column(
        pg_enum(EstadoConsulta, "estado_consulta"),
        default=EstadoConsulta.ABIERTA,
        server_default=EstadoConsulta.ABIERTA.value,
    )
    presupuesto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fecha_deseada: Mapped[date | None] = mapped_column(Date, nullable=True)
    # La marca del ultimo mensaje. Ordena la bandeja
    ultimo_mensaje_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    # Hasta donde leyo cada lado. Nulo: no leyo nada
    leido_cliente_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    leido_artista_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Mensaje(Base, IdMixin, TimestampMixin):
    """Unico mecanismo de chat del sistema."""

    __tablename__ = "mensajes"
    __table_args__ = (
        # Historial y mensajes nuevos de una consulta, en el orden del cursor
        Index("ix_mensajes_consulta_id_created_at", "consulta_id", "created_at", "id"),
    )

    # Sin indice propio: lo cubre ix_mensajes_consulta_id_created_at
    consulta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("consultas.id"))
    remitente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    texto: Mapped[str] = mapped_column(String)
    # Telefono, WhatsApp o SINPE: no se rechaza, se avisa a los dos lados
    aviso_contacto: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
