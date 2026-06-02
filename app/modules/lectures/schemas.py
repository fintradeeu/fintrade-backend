"""Lectures module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LectureCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    course_id: int
    instructor_id: Optional[int] = None
    meeting_link: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int = 60
    max_participants: int = 0

class LectureUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    course_id: Optional[int] = None
    instructor_id: Optional[int] = None
    meeting_link: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    max_participants: Optional[int] = None
    status: Optional[str] = None

class RecordingCreate(BaseModel):
    recording_url: str = Field(..., max_length=1000)
    duration_seconds: Optional[int] = None
    file_size_mb: Optional[int] = None


class RecordingResponse(BaseModel):
    id: int
    recording_url: str
    duration_seconds: Optional[int] = None
    file_size_mb: Optional[int] = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class LectureResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_id: int
    instructor_id: Optional[int] = None
    meeting_link: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    is_live: bool
    is_completed: bool
    max_participants: int
    recordings: List[RecordingResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class LectureJoinResponse(BaseModel):
    lecture_id: int
    meeting_link: str
    message: str


class MessageResponse(BaseModel):
    message: str
