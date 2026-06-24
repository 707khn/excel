from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ExcelFileOut(BaseModel):
    id: int
    filename: str
    description: Optional[str]
    file_size: Optional[int]
    has_content: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExcelFileWithAccess(ExcelFileOut):
    access_level: str


class FileContentResponse(BaseModel):
    content: str  # base64-encoded xlsx bytes
    filename: str
    access_level: str


class FileSaveRequest(BaseModel):
    content: str  # base64-encoded xlsx bytes
