from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int]
    user_email: str
    action: str
    file_id: Optional[int]
    file_name: str
    ip_address: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogPage(BaseModel):
    items: List[AuditLogOut]
    total: int
    page: int
    limit: int
