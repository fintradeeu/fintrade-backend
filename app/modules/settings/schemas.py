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


class AboutUsConfig(BaseModel):
    slides: Optional[List[str]] = None
    stats: Optional[List[Dict[str, Any]]] = None
    text: Optional[List[str]] = None
    vision: Optional[Dict[str, Any]] = None
    mission: Optional[Dict[str, Any]] = None
    leadership: Optional[List[Dict[str, Any]]] = None


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
    hero_buttons: Optional[Dict[str, Any]] = None
    carousel_slides: Optional[List[Dict[str, Any]]] = None
    section_visibility: Optional[Dict[str, Any]] = None
    live_classes: Optional[List[Dict[str, Any]]] = None
    emi: Optional[Dict[str, Any]] = None
    certificate: Optional[Dict[str, Any]] = None
    program_modules: Optional[List[Dict[str, Any]]] = None
    hero_backgrounds: Optional[List[str]] = None
    about_us_slides: Optional[List[str]] = None
    about_us_stats: Optional[List[Dict[str, Any]]] = None
    about_us_text: Optional[List[str]] = None
    about_us_vision: Optional[Dict[str, Any]] = None
    about_us_mission: Optional[Dict[str, Any]] = None


class SettingsGroupedResponse(BaseModel):
    general: List[SettingResponse] = []
    simulator: List[SettingResponse] = []
    exam: List[SettingResponse] = []
    payment: List[SettingResponse] = []


class MessageResponse(BaseModel):
    message: str

