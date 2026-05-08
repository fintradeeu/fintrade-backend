"""Courses module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enrollment request ───────────────────────────────────────────────
class EnrollRequest(BaseModel):
    distributor_code: Optional[str] = Field(None, description="Optional distributor referral code")
    model_config = {"extra": "forbid"}


# ── Lesson ───────────────────────────────────────────────────────────
class LessonCreate(BaseModel):
    module_id: int
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    content_type: str = Field("text", max_length=50)
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order: int = 0
    is_published: bool = False


class LessonResponse(BaseModel):
    id: int
    module_id: int
    title: str
    content: Optional[str] = None
    content_type: str
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order: int
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Module ───────────────────────────────────────────────────────────
class ModuleCreate(BaseModel):
    course_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    order: int = 0
    is_published: bool = False


class ModuleResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    order: int
    is_published: bool
    lessons: List[LessonResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Course ───────────────────────────────────────────────────────────
class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    thumbnail_url: Optional[str] = None
    price: float = 0.0
    difficulty_level: str = "beginner"
    duration_hours: Optional[int] = None
    is_published: bool = False
    instructor_id: Optional[int] = None

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    thumbnail_url: Optional[str] = None
    price: Optional[float] = None
    difficulty_level: Optional[str] = None
    duration_hours: Optional[int] = None
    is_published: Optional[bool] = None


class CourseListResponse(BaseModel):
    id: int
    title: str
    slug: str
    short_description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: float
    difficulty_level: str
    duration_hours: Optional[int] = None
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseDetailResponse(BaseModel):
    id: int
    title: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: float
    difficulty_level: str
    duration_hours: Optional[int] = None
    is_published: bool
    modules: List[ModuleResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Enrollment ───────────────────────────────────────────────────────
class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: datetime
    is_active: bool
    progress_percent: float
    completed_at: Optional[datetime] = None
    discount_applied: float = 0.0
    price_paid: Optional[float] = None
    course: CourseListResponse

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
