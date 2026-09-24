import enum
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ProfileRole(enum.StrEnum):
    ARTISTA = "artista"
    ADMIN = "admin"


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    # ID proveniente de Supabase auth.users
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    handle: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[ProfileRole] = mapped_column(
        ENUM(
            ProfileRole,
            name="profile_role_enum",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ProfileRole.ARTISTA,
    )


class Follow(Base, TimestampMixin):
    __tablename__ = "follows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    follower_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    following_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
