"""Feedback module — Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackFormCreateRequest(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    course_id: int
    is_active: bool = True


class FeedbackFormUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    course_id: Optional[int] = None
    is_active: Optional[bool] = None


class FeedbackFormResponse(BaseModel):
    id: int
    token: Optional[str] = None
    title: str
    description: Optional[str] = None
    course_id: int
    course_title: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedbackCreateRequest(BaseModel):
    course_id: Optional[int] = None
    form_id: Optional[int] = None
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    form_id: Optional[int] = None
    course_id: Optional[int] = None
    rating: int
    comments: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    show_on_landing_page: bool = False
    course_title: Optional[str] = None
    user_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
