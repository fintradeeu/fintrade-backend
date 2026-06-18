"""Admin module — Pydantic schemas for admin-specific responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.schemas import UserResponse


class AdminStatsResponse(BaseModel):
    total_users: int
    total_courses: int
    total_enrollments: int
    total_exams: int
    total_lectures: int
    total_distributors: int


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class MessageResponse(BaseModel):
    message: str


# ── User creation requests ──────────────────────────────────────────
class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    permissions: Optional[dict] = None


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    permissions: Optional[dict] = None
    # For distributor update
    region: Optional[str] = Field(None, min_length=1, max_length=255)
    referral_code: Optional[str] = Field(None, min_length=3, max_length=50)
    discount_percentage: Optional[float] = Field(None, ge=0, le=100)


class CreateDistributorRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    region: str = Field(..., min_length=1, max_length=255)
    referral_code: Optional[str] = Field(None, max_length=50)
    discount_percentage: float = Field(0.0, ge=0, le=100)


# ── Distributor responses ───────────────────────────────────────────
class AdminDistributorResponse(BaseModel):
    id: int
    user_id: int
    region: str
    referral_code: str
    discount_percentage: float
    created_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    total_students_referred: int = 0
    total_revenue_generated: float = 0.0

    model_config = {"from_attributes": True}


class AdminDistributorStatsResponse(BaseModel):
    distributor_id: int
    region: str
    referral_code: str
    user_name: Optional[str] = None
    total_students_referred: int
    total_courses_purchased: int
    total_revenue_generated: float


# ── Phase 3: Admin Report Schemas ────────────────────────────────────

class AdminReportsResponse(BaseModel):
    total_students: int
    total_courses: int
    total_certificates: int
    total_simulator_accounts: int
    total_feedback: int
    avg_feedback_rating: float
    total_placements_eligible: int


class AdminCertificateItem(BaseModel):
    id: int
    user_id: int
    course_id: int
    unique_code: str
    issued_at: datetime

    model_config = {"from_attributes": True}


class AdminCertificatesResponse(BaseModel):
    total: int
    certificates: List[AdminCertificateItem]


class AdminSimulatorItem(BaseModel):
    user_id: int
    balance: float
    total_pnl: float
    win_rate: float
    total_trades: int


class AdminSimulatorResponse(BaseModel):
    total_accounts: int
    top_performers: List[AdminSimulatorItem]

