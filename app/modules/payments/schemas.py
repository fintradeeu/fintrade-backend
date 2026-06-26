"""Payments module — schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PaymentInitiateRequest(BaseModel):
    course_id: int
    coupon_code: Optional[str] = None
    discounted_price: Optional[float] = None

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
