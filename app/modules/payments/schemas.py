"""Payments module — schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PaymentInitiateRequest(BaseModel):
    course_id: int
    coupon_code: Optional[str] = None
    discounted_price: Optional[float] = None
    batch_id: Optional[int] = None

class PaymentInitiateResponse(BaseModel):
    txnid: str
    access_key: Optional[str] = None
    redirect_url: Optional[str] = None
    gateway: Optional[str] = None
    key_id: Optional[str] = None
    order_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None

class RazorpayVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    txnid: Optional[str] = None

class PaymentTransactionResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    txnid: str
    easepayid: Optional[str] = None
    amount: float
    status: str
    payment_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OfflinePaymentRequest(BaseModel):
    course_id: int
    payment_mode: str # 'cash' or 'cheque'
    amount: float
    reference_number: Optional[str] = None
    payment_date: Optional[datetime] = None
    bank_name: Optional[str] = None
    branch_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    cheque_image_url: Optional[str] = None
    remarks: Optional[str] = None
    coupon_code: Optional[str] = None
    batch_id: Optional[int] = None

class OfflinePaymentApprovalRequest(BaseModel):
    action: str # 'approve' or 'reject'
    reason: Optional[str] = None
