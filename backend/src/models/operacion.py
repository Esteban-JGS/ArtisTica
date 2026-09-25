import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin, pg_enum


class EstadoReporte(enum.StrEnum):
    PENDIENTE = "pendiente"
    REVISADO = "revisado"
    DESCARTADO = "descartado"


class Job(Base, IdMixin, TimestampMixin):
    # El worker depende de esta forma exacta
    __tablename__ = "jobs"

    type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)


class Reporte(Base, IdMixin, TimestampMixin):
    __tablename__ = "reportes"

    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(String)
    estado: Mapped[EstadoReporte] = mapped_column(
        pg_enum(EstadoReporte, "estado_reporte"), default=EstadoReporte.PENDIENTE
    )


class ModerationAction(Base, IdMixin, TimestampMixin):
    __tablename__ = "moderation_actions"

    admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String)
    nota: Mapped[str | None] = mapped_column(String, nullable=True)
