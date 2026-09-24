import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfileBase(BaseModel):
    handle: str
    name: str
    bio: str | None = None
    categories: list[str] = []


class ProfileCreate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: uuid.UUID
    is_verified: bool
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
