import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class PostView(Base, IdMixin, TimestampMixin):
    """Una vista por usuario, publicacion y dia. Impide inflar las vistas."""

    __tablename__ = "post_views"
    __table_args__ = (UniqueConstraint("publicacion_id", "profile_id", "dia"),)

    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    dia: Mapped[date] = mapped_column(Date)
