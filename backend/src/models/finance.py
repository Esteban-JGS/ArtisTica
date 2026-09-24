import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LedgerEntry(Base, TimestampMixin):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    commission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("commissions.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    type: Mapped[str] = mapped_column(String)  # 'debit' or 'credit'
    description: Mapped[str] = mapped_column(String)


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    commission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commissions.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    gateway_reference: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)


class Payout(Base, TimestampMixin):
    __tablename__ = "payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String)
    gateway_reference: Mapped[str | None] = mapped_column(String, nullable=True)
