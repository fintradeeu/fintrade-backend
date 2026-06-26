"""Dashboard module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Announcements ────────────────────────────────────────────────────

class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    priority: str = Field("normal", pattern="^(low|normal|high|urgent)$")
    is_active: bool = True
    expires_at: Optional[datetime] = None


class AnnouncementUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|normal|high|urgent)$")
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    priority: str
    is_active: bool
    created_by: Optional[int] = None
    published_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Advertisements ───────────────────────────────────────────────────

class AdvertisementCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    placement: str = Field("dashboard", pattern="^(dashboard|sidebar|banner)$")
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AdvertisementUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    placement: Optional[str] = Field(None, pattern="^(dashboard|sidebar|banner)$")
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AdvertisementResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    placement: str
    is_active: bool
    created_by: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


# ── Leaderboard ──────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    id: int
    name: str
    score: int
    rank: int
    badge: str


class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]
    my_rank: int
    my_score: int
