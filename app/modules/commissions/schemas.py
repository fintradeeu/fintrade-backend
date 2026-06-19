"""Schemas for IB commission and wallet APIs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class CourseCommissionSummary(BaseModel):
    course_id: int
    course_title: str
    course_price: float
    total_ibs: int
    configured_ibs: int


class CommissionUpsertRequest(BaseModel):
    commission_type: str = Field(..., pattern="^(flat|percentage)$")
    commission_value: float = Field(..., ge=0)
    is_active: bool = True


class IBCommissionRow(BaseModel):
    ib_id: int
    user_id: int
    ib_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    commission_id: Optional[int] = None
    commission_type: Optional[str] = None
    commission_value: Optional[float] = None
    is_active: bool = False


class WalletSummary(BaseModel):
    ib_id: int
    available_balance: float
    total_earned: float
    total_withdrawn: float
    pending_withdrawals: float


class WalletTransactionResponse(BaseModel):
    id: int
    ib_id: int
    student_name: Optional[str] = None
    course_title: Optional[str] = None
    commission_amount: float
    transaction_type: str
    description: Optional[str] = None
    reference_no: Optional[str] = None
    status: str
    balance_after: float
    created_at: datetime

    model_config = {"from_attributes": True}


class WithdrawalCreateRequest(BaseModel):
    amount: float = Field(..., ge=500)
    withdrawal_method: str = Field(..., pattern="^(bank|upi)$")
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    confirm_account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    qr_code_image: Optional[str] = None

    @model_validator(mode="after")
    def validate_method(self):
        if self.withdrawal_method == "bank":
            if not all([self.account_holder_name, self.bank_name, self.account_number, self.confirm_account_number, self.ifsc_code]):
                raise ValueError("Bank withdrawal requires account holder, bank name, account number, confirm account number, and IFSC code")
            if self.account_number != self.confirm_account_number:
                raise ValueError("Account number and confirm account number do not match")
        if self.withdrawal_method == "upi" and not (self.upi_id or self.qr_code_image):
            raise ValueError("UPI withdrawal requires UPI ID or QR code")
        return self


class WithdrawalActionRequest(BaseModel):
    admin_remarks: Optional[str] = None


class WithdrawalResponse(BaseModel):
    id: int
    ib_id: int
    ib_name: Optional[str] = None
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

    model_config = {"from_attributes": True}


class CommissionReport(BaseModel):
    total_sales: float
    total_commission: float
    total_paid: float
    pending_commission: float


class WithdrawalReport(BaseModel):
    requested_amount: float
    paid_amount: float
    pending_amount: float
