import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import EstadoOnboarding, PlanArtista, RolPerfil

from .base import Base, IdMixin, TimestampMixin, pg_enum


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"
    __table_args__ = (
        # Filtro por categorias de Explorar, con el operador &&
        Index("ix_profiles_categorias", "categorias", postgresql_using="gin"),
    )

    # El id viene de auth.users de Supabase
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    handle: Mapped[str] = mapped_column(String, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    categorias: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default=text("'{}'")
    )
    provincia: Mapped[str | None] = mapped_column(String, nullable=True)
    rol: Mapped[RolPerfil] = mapped_column(
        pg_enum(RolPerfil, "rol_perfil"),
        default=RolPerfil.PUBLICO,
        server_default=RolPerfil.PUBLICO.value,
    )
    plan: Mapped[PlanArtista] = mapped_column(
        pg_enum(PlanArtista, "plan_artista"),
        default=PlanArtista.TALLER,
        server_default=PlanArtista.TALLER.value,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    pasarela_cuenta_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pasarela_onboarding: Mapped[EstadoOnboarding] = mapped_column(
        pg_enum(EstadoOnboarding, "estado_onboarding"),
        default=EstadoOnboarding.NO_INICIADO,
        server_default=EstadoOnboarding.NO_INICIADO.value,
    )


class Follow(Base, IdMixin, TimestampMixin):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("seguidor_id", "seguido_id"),
        CheckConstraint("seguidor_id <> seguido_id", name="no_autoseguimiento"),
    )

    seguidor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    seguido_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
