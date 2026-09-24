import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.commissions import CommissionState


class CommissionCreate(BaseModel):
    artist_id: uuid.UUID
    description: str


class CommissionResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    artist_id: uuid.UUID
    description: str
    price: float | None = None
    status: CommissionState
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommissionMessageCreate(BaseModel):
    content: str


class CommissionMessageResponse(BaseModel):
    id: uuid.UUID
    commission_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
