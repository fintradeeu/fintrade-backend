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

    class Config:
        from_attributes = True
