"""Certificates module — Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CertificateGenerateRequest(BaseModel):
    course_id: int


class CertificateResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    course_title: Optional[str] = None
    certificate_number: Optional[str] = None
    unique_code: str
    certificate_url: Optional[str] = None
    issued_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
