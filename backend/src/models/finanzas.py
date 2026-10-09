import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class LedgerEntry(Base, IdMixin, TimestampMixin):
    """Registro de conciliacion. Cada fila es un hecho de la pasarela y no se edita."""

    __tablename__ = "ledger_entries"

    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pedidos.id"), nullable=True, index=True
    )
    cobro_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cobros.id"), nullable=True, index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    # Un hecho se asienta una sola vez: repetirlo choca con la restriccion
    clave: Mapped[str] = mapped_column(String, unique=True)
    tipo_evento: Mapped[str] = mapped_column(String)
    monto_bruto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Nulos cuando la pasarela no los informa
    tarifa_artistica: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    costo_procesamiento: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    monto_neto_artista: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    referencia_pasarela: Mapped[str | None] = mapped_column(String, nullable=True)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventoPasarela(Base, IdMixin, TimestampMixin):
    """Webhooks recibidos. La restriccion unica da la idempotencia."""

    __tablename__ = "eventos_pasarela"
    __table_args__ = (
        UniqueConstraint("proveedor", "evento_externo_id"),
        # Los que el barrido tiene que reintentar
        Index(
            "ix_eventos_pasarela_pendientes",
            "created_at",
            postgresql_where=text("procesado_en IS NULL"),
        ),
    )

    proveedor: Mapped[str] = mapped_column(String)
    evento_externo_id: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    # El cobro del evento, si el proveedor lo informa. Sensible: no sale en
    # ninguna respuesta
    referencia: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    procesado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Intentos de proceso fallidos
    intentos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String, nullable=True)
