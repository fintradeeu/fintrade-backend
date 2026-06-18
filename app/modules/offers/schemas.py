"""Offers module — Pydantic schemas."""

from datetime import datetime
from typing import Optional

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field


class OfferCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    discount_type: str = "percentage"  # percentage or fixed
    discount_value: float = Field(..., gt=0)
    code: str = Field(..., min_length=3, max_length=50)
    course_id: Optional[int] = None
    max_redemptions: int = 0
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class OfferResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    code: str
    course_id: Optional[int] = None
    max_redemptions: int
    current_redemptions: int
    is_active: bool
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OfferApplyRequest(BaseModel):
    code: Optional[str] = None
    course_id: int


class OfferApplyResponse(BaseModel):
    offer_id: int
    original_price: float
    discounted_price: float
    discount_applied: float
    message: str


class MessageResponse(BaseModel):
    message: str
