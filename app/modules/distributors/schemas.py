"""Distributors module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class DistributorProfileResponse(BaseModel):
    id: int
    user_id: int
    region: str
    referral_code: str
    discount_percentage: float
    created_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    profile_photo_url: Optional[str] = None
    aadhaar_card_url: Optional[str] = None
    pan_card_url: Optional[str] = None
    bank_account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_upi_id: Optional[str] = None
    self_registered: Optional[str] = None
    verification_status: Optional[str] = None

    model_config = {"from_attributes": True}


class ReferralCodeResponse(BaseModel):
    referral_code: str
    discount_percentage: float
    region: str


class ReferralResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    mobile_no: Optional[str] = None
    city: Optional[str] = None
    course_id: Optional[int] = None
    course_title: Optional[str] = None
    registered: bool = False
    entrance_exam_given: bool = False
    entrance_exam_course_title: Optional[str] = None
    entrance_exam_score: Optional[float] = None
    entrance_exam_passed: Optional[bool] = None
    kyc_done: bool = False
    kyc_status: Optional[str] = None
    enrolled: bool = False
    fees_paid: bool = False
    enrolled_courses: List[str] = []
    course_completed: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralLeadCreate(BaseModel):
    referral_code: str = Field(..., min_length=2, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    mobile_no: str = Field(..., min_length=8, max_length=50)
    city: Optional[str] = Field(None, max_length=100)


class ReferralLeadResponse(BaseModel):
    id: int
    referral_code: str
    full_name: str
    email: str
    mobile_no: str
    city: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DistributorSelfRegisterResponse(BaseModel):
    message: str
    referral_code: str
    verification_status: str


class DistributorStatsResponse(BaseModel):
    distributor_id: int
    region: str
    referral_code: str
    total_students_referred: int
    total_courses_purchased: int
    total_revenue_generated: float


class MessageResponse(BaseModel):
    message: str


class ManualStudentRegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    city: Optional[str] = None
    course_id: Optional[int] = None
    payment_mode: str = "razorpay" # razorpay, cash, cheque
    amount: float = 0.0
    reference_number: Optional[str] = None
    cheque_image_url: Optional[str] = None
    remarks: Optional[str] = None
