"""Franchise IBs module — Pydantic schemas."""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class FranchiseIBCreate(BaseModel):
    full_name: str
    email: EmailStr
    mobile_no: str
    password: str
    
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    
    bank_account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None


class FranchiseIBResponse(BaseModel):
    id: int
    user_id: int
    referral_code: str
    verification_status: str
    created_at: datetime
    
    pan_number: Optional[str] = None
    aadhaar_number: Optional[str] = None
    
    bank_account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None

    class Config:
        from_attributes = True


class ChartDataPoint(BaseModel):
    name: str
    value: float

class FranchiseIBDashboardStats(BaseModel):
    referral_code: Optional[str] = None
    total_students: int
    active_students: int
    total_ibs: int
    today_registrations: int
    monthly_registrations: int
    pending_payments: int
    total_enrollments: int
    
    total_revenue: float
    razorpay_revenue: float
    cash_revenue: float
    cheque_revenue: float
    
    revenue_chart_data: List[ChartDataPoint] = []
    enrollment_chart_data: List[ChartDataPoint] = []
