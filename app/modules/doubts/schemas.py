"""Doubts module — Pydantic schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class DoubtFormCreate(BaseModel):
    title: str
    description: Optional[str] = None
    batch_id: int
    end_date: datetime
    is_active: bool = True


class DoubtFormUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class BatchInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class DoubtFormResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    batch_id: int
    batch: Optional[BatchInfo]
    end_date: datetime
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    submission_count: int = 0

    class Config:
        from_attributes = True


class DoubtSubmissionCreate(BaseModel):
    topic: Optional[str] = None
    doubt_text: str


class StudentInfo(BaseModel):
    id: int
    full_name: Optional[str]
    email: str
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class DoubtSubmissionResponse(BaseModel):
    id: int
    form_id: int
    student_id: int
    student: Optional[StudentInfo]
    topic: Optional[str]
    doubt_text: str
    submitted_at: datetime

    class Config:
        from_attributes = True
