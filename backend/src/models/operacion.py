import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import EstadoReporte

from .base import Base, IdMixin, TimestampMixin, pg_enum


class Job(Base, IdMixin, TimestampMixin):
    # El worker depende de esta forma exacta
    __tablename__ = "jobs"

    type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending", index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)


class Reporte(Base, IdMixin, TimestampMixin):
    __tablename__ = "reportes"

    # Nula si se borra la cuenta: el reporte sobrevive
    reportante_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    objetivo_tipo: Mapped[str] = mapped_column(String)
    objetivo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    motivo: Mapped[str] = mapped_column(String)
    estado: Mapped[EstadoReporte] = mapped_column(
        pg_enum(EstadoReporte, "estado_reporte"),
        default=EstadoReporte.PENDIENTE,
        server_default=EstadoReporte.PENDIENTE.value,
    )


class AccionModeracion(Base, IdMixin, TimestampMixin):
    __tablename__ = "acciones_moderacion"

    # Nula si se borra la cuenta: el historial sobrevive
    moderador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    objetivo_tipo: Mapped[str] = mapped_column(String)
    objetivo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    accion: Mapped[str] = mapped_column(String)
    nota: Mapped[str | None] = mapped_column(String, nullable=True)
