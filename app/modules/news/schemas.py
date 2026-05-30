"""News module — Pydantic schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class NewsCreateRequest(BaseModel):
    title: str
    type: Literal["Blog Story", "Market Update"] = "Blog Story"
    description: Optional[str] = None
    video_type: str = "youtube"  # youtube or uploaded
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str = "published"  # published or draft


class NewsUpdateRequest(BaseModel):
    title: Optional[str] = None
    type: Optional[Literal["Blog Story", "Market Update"]] = None
    description: Optional[str] = None
    video_type: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: Optional[str] = None


class NewsResponse(BaseModel):
    id: int
    title: str
    type: Literal["Blog Story", "Market Update"] = "Blog Story"
    description: Optional[str] = None
    video_type: str = "youtube"
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str = "published"
    views_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NewsStatsResponse(BaseModel):
    total_articles: int = 0
    youtube_count: int = 0
    uploaded_count: int = 0
    total_views: int = 0
    draft_count: int = 0


class MessageResponse(BaseModel):
    message: str
