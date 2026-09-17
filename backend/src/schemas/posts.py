from pydantic import BaseModel, ConfigDict
import uuid
from datetime import datetime
from typing import Optional, List
from src.schemas.media import MediaAssetResponse

class PostBase(BaseModel):
    content: str

class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    id: uuid.UUID
    profile_id: uuid.UUID
    content: str
    created_at: datetime
    
    # Lista de assets incluidos opcionalmente en la respuesta
    assets: List[MediaAssetResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
