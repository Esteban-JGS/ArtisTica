import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SignedUrlResponse(BaseModel):
    upload_url: str
    asset_id: uuid.UUID
    storage_path: str


class AssetRegisterRequest(BaseModel):
    asset_id: uuid.UUID
    post_id: uuid.UUID | None = None


class MediaAssetResponse(BaseModel):
    id: uuid.UUID
    type: str
    storage_path: str
    thumbnail_path: str | None = None
    processing_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
