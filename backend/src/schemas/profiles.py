from pydantic import BaseModel, ConfigDict
import uuid
from typing import List, Optional
from datetime import datetime

class ProfileBase(BaseModel):
    handle: str
    name: str
    bio: Optional[str] = None
    categories: List[str] = []

class ProfileCreate(ProfileBase):
    pass

class ProfileResponse(ProfileBase):
    id: uuid.UUID
    is_verified: bool
    role: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
