"""News module — Pydantic schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class NewsCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: Literal["Market Update", "Blog Story"] = "Blog Story"
    description: Optional[str] = None
    author_name: Optional[str] = Field(None, max_length=255)
    video_url: Optional[str] = None        # Only relevant for Market Updates
    thumbnail_url: Optional[str] = None
    status: Literal["published", "draft"] = "published"


class NewsUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    type: Optional[Literal["Market Update", "Blog Story"]] = None
    description: Optional[str] = None
    author_name: Optional[str] = Field(None, max_length=255)
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: Optional[Literal["published", "draft"]] = None


# ── Response schemas ─────────────────────────────────────────────────────────

class NewsResponse(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = None
    author_name: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str
    views_count: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NewsStatsResponse(BaseModel):
    total_articles: int = 0
    market_update_count: int = 0
    blog_story_count: int = 0
    published_count: int = 0
    draft_count: int = 0
    total_views: int = 0


class MessageResponse(BaseModel):
    message: str
