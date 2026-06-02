"""AI chatbot module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = None
    course_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AskResponse(BaseModel):
    session_id: int
    answer: str
    sources: List[str] = []


class ChatSessionResponse(BaseModel):
    id: int
    title: Optional[str] = None
    is_active: bool
    created_at: datetime
    messages: List[ChatMessageResponse] = []

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    sessions: List[ChatSessionResponse]


class FAQCreate(BaseModel):
    question: str
    answer: str
    category_id: Optional[int] = None
    course_id: Optional[int] = None
    is_active: bool = True


class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category_id: Optional[int] = None
    course_id: Optional[int] = None
    is_active: Optional[bool] = None


class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    category_id: Optional[int] = None
    course_id: Optional[int] = None
    is_active: bool
    frequency: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
