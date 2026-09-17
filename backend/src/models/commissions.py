import uuid
import enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID
from .base import Base, TimestampMixin

class CommissionState(str, enum.Enum):
    SOLICITADA = "solicitada"
    COTIZADA = "cotizada"
    ACEPTADA = "aceptada"
    PAGADA_EN_RETENCION = "pagada_en_retencion"
    ENTREGADA = "entregada"
    LIBERADA = "liberada"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"
    EN_DISPUTA = "en_disputa"

# Diccionario de transiciones válidas documentado
COMMISSION_TRANSITIONS = {
    CommissionState.SOLICITADA: [CommissionState.COTIZADA, CommissionState.RECHAZADA],
    CommissionState.COTIZADA: [CommissionState.ACEPTADA, CommissionState.RECHAZADA],
    CommissionState.ACEPTADA: [CommissionState.PAGADA_EN_RETENCION, CommissionState.CANCELADA],
    CommissionState.PAGADA_EN_RETENCION: [CommissionState.ENTREGADA],
    CommissionState.ENTREGADA: [CommissionState.LIBERADA, CommissionState.EN_DISPUTA],
    CommissionState.LIBERADA: [],
    CommissionState.RECHAZADA: [],
    CommissionState.CANCELADA: [],
    CommissionState.EN_DISPUTA: [CommissionState.LIBERADA, CommissionState.CANCELADA],
}

class Commission(Base, TimestampMixin):
    __tablename__ = "commissions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    description: Mapped[str] = mapped_column(String)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CommissionState] = mapped_column(
        Enum(CommissionState, name="commission_state_enum", create_type=False), 
        default=CommissionState.SOLICITADA
    )

class CommissionMessage(Base, TimestampMixin):
    __tablename__ = "commission_messages"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commissions.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    content: Mapped[str] = mapped_column(String)

class CommissionDeliverable(Base, TimestampMixin):
    __tablename__ = "commission_deliverables"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commissions.id", ondelete="CASCADE"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id"))
