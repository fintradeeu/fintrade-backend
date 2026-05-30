"""Settings module — Pydantic schemas."""

from datetime import datetime
from typing import Optional, Dict, List, Any

from pydantic import BaseModel


class SettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str] = None
    category: str = "general"
    label: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SettingUpdateRequest(BaseModel):
    value: str


class BulkSettingUpdateRequest(BaseModel):
    settings: Dict[str, str]  # key -> value pairs


class LandingPageUpdateRequest(BaseModel):
    hero: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    social: Optional[Dict[str, Any]] = None
    showcase_videos: Optional[List[Dict[str, Any]]] = None
    benefits: Optional[List[Dict[str, Any]]] = None
    services: Optional[List[Dict[str, Any]]] = None
    quick_tips: Optional[List[Dict[str, Any]]] = None
    why_choose: Optional[List[Dict[str, Any]]] = None
    leadership: Optional[List[Dict[str, Any]]] = None


class SettingsGroupedResponse(BaseModel):
    general: List[SettingResponse] = []
    simulator: List[SettingResponse] = []
    exam: List[SettingResponse] = []
    payment: List[SettingResponse] = []


class MessageResponse(BaseModel):
    message: str

