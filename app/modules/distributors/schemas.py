"""Distributors module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DistributorProfileResponse(BaseModel):
    id: int
    user_id: int
    region: str
    referral_code: str
    discount_percentage: float
    created_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


class ReferralCodeResponse(BaseModel):
    referral_code: str
    discount_percentage: float
    region: str


class ReferralResponse(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    course_id: Optional[int] = None
    course_title: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DistributorStatsResponse(BaseModel):
    distributor_id: int
    region: str
    referral_code: str
    total_students_referred: int
    total_courses_purchased: int
    total_revenue_generated: float


class MessageResponse(BaseModel):
    message: str
