from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Optional
from datetime import datetime

class URLCreate(BaseModel):
    url: HttpUrl
    expires_in_days: Optional[int] = None
    custom_alias: Optional[str] = None


class URLInfo(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime]
    click_count: int

    # Pydantic v2 style
    model_config = ConfigDict(from_attributes=True)


class ErrorLogInfo(BaseModel):
    path: str
    method: str
    status_code: int
    detail: str
    created_at: datetime

    # Pydantic v2 style
    model_config = ConfigDict(from_attributes=True)
