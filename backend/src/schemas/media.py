from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional
from datetime import datetime

class SignedUrlResponse(BaseModel):
    upload_url: str
    asset_id: uuid.UUID
    storage_path: str

class AssetRegisterRequest(BaseModel):
    asset_id: uuid.UUID
    post_id: Optional[uuid.UUID] = None

class MediaAssetResponse(BaseModel):
    id: uuid.UUID
    type: str
    storage_path: str
    thumbnail_path: Optional[str] = None
    processing_status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
