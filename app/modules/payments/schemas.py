"""Payments module — schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PaymentInitiateRequest(BaseModel):
    course_id: int

class PaymentInitiateResponse(BaseModel):
    txnid: str
    access_key: str
    redirect_url: str

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

