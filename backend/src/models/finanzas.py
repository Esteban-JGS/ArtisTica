import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class LedgerEntry(Base, IdMixin, TimestampMixin):
    """Registro de conciliacion. Cada fila es un hecho de la pasarela y no se edita."""

    __tablename__ = "ledger_entries"

    pedido_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pedidos.id"), nullable=True
    )
    cobro_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cobros.id"), nullable=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    tipo_evento: Mapped[str] = mapped_column(String)
    monto_bruto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tarifa_artistica: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    costo_procesamiento: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monto_neto_artista: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    referencia_pasarela: Mapped[str | None] = mapped_column(String, nullable=True)
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventoPasarela(Base, IdMixin, TimestampMixin):
    """Webhooks recibidos. La restriccion unica da la idempotencia."""

    __tablename__ = "eventos_pasarela"
    __table_args__ = (UniqueConstraint("proveedor", "evento_externo_id"),)

    proveedor: Mapped[str] = mapped_column(String)
    evento_externo_id: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB)
    procesado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(String, nullable=True)
