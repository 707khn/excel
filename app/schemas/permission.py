from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PermissionCreate(BaseModel):
    user_id: int
    access_level: str  # "read" or "write"


class PermissionOut(BaseModel):
    id: int
    user_id: int
    file_id: int
    access_level: str
    granted_by: Optional[int]
    granted_at: datetime

    model_config = {"from_attributes": True}


class PermissionWithUser(PermissionOut):
    user_email: str
    user_full_name: str
