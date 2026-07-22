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
    commission_percentage: Optional[float] = 100.0


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
    commission_percentage: float

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


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None


class FranchiseIBWithdrawalCreateRequest(BaseModel):
    amount: float
    withdrawal_method: str  # bank, upi
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    confirm_account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    qr_code_image: Optional[str] = None


class FranchiseIBWithdrawalResponse(BaseModel):
    id: int
    franchise_ib_id: int
    franchise_ib_name: Optional[str] = None
    amount: float
    withdrawal_method: str
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    qr_code_image: Optional[str] = None
    status: str
    requested_at: datetime
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    admin_remarks: Optional[str] = None
    payment_proof: Optional[str] = None
    utr_number: Optional[str] = None
    transaction_reference: Optional[str] = None

    class Config:
        from_attributes = True


class FranchiseIBWalletSummary(BaseModel):
    available_balance: float
    total_earned: float
    total_withdrawn: float
    pending_withdrawals: float

