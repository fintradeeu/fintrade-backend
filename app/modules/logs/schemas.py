from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime

class ActivityLogCreate(BaseModel):
    module: str
    action: str
    description: Optional[str] = None
    status_code: Optional[int] = None
    status_text: Optional[str] = None
    location_data: Optional[Dict[str, Any]] = None
    device_data: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    suspicious: Optional[bool] = False

class UserBase(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True

class ActivityLogMetadataResponse(BaseModel):
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    device_type: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    ip_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    permission_status: Optional[str] = None
    app_version: Optional[str] = None
    build_number: Optional[str] = None

    class Config:
        from_attributes = True

class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    module: str
    action: str
    description: Optional[str] = None
    status_code: Optional[int] = None
    status_text: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location_data: Optional[Dict[str, Any]] = None
    device_data: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    suspicious: bool
    created_at: datetime
    
    user: Optional[UserBase] = None
    log_metadata: Optional[ActivityLogMetadataResponse] = None

    class Config:
        from_attributes = True
