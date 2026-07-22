"""Offers module — API routes."""

from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.courses.models import Course
from app.modules.offers import schemas, services
from app.modules.offers.models import Offer
from app.modules.distributors.models import Distributor

router = APIRouter(prefix="/offers", tags=["Offers"])


@router.get("", response_model=List[schemas.OfferResponse])
async def list_offers(db: AsyncSession = Depends(get_db)):
    """List all active offers."""
    offers = await services.list_offers(db)
    return [schemas.OfferResponse.model_validate(o) for o in offers]


@router.post("/apply", response_model=schemas.OfferApplyResponse)
async def apply_offer(
    body: schemas.OfferApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply an offer code to a course."""
    result = await services.apply_offer(db, current_user.id, body.code, body.course_id)
    return schemas.OfferApplyResponse(**result)


@router.post("/validate")
async def validate_offer(
    body: schemas.OfferApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate an offer or referral coupon code without consuming a redemption."""
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Coupon code is required")
    
    # 1. Check Offer table
    result = await db.execute(select(Offer).where(Offer.code == code))
    offer = result.scalar_one_or_none()
    
    course_price = 0.0
    if body.course_id:
        course = await db.get(Course, body.course_id)
        if course:
            course_price = course.price or 0.0
            
    if offer:
        if not offer.is_active:
            raise HTTPException(status_code=400, detail="This coupon code is currently inactive")
        now = datetime.now(timezone.utc)
        if offer.valid_until and now > offer.valid_until:
            raise HTTPException(status_code=400, detail="This coupon code has expired")
        if offer.max_redemptions > 0 and offer.current_redemptions >= offer.max_redemptions:
            raise HTTPException(status_code=400, detail="This coupon code usage limit has been reached")
            
        discount_amount = 0.0
        if offer.discount_type == "percentage":
            discount_amount = round(course_price * (offer.discount_value / 100.0), 2)
        else:
            discount_amount = round(offer.discount_value, 2)
            
        return {
            "valid": True,
            "code": offer.code,
            "title": offer.title,
            "discount_type": offer.discount_type,
            "discount_value": offer.discount_value,
            "discount_amount": discount_amount,
            "discounted_price": max(0.0, course_price - discount_amount),
        }
        
    # 2. Check Distributor / Franchise IB referral codes
    dist_res = await db.execute(select(Distributor).where(Distributor.referral_code == code))
    dist = dist_res.scalar_one_or_none()
    if dist:
        disc_pct = dist.discount_percentage or 10.0
        discount_amount = round(course_price * (disc_pct / 100.0), 2)
        return {
            "valid": True,
            "code": dist.referral_code,
            "title": f"Referral Code ({dist.region or 'IB'})",
            "discount_type": "percentage",
            "discount_value": disc_pct,
            "discount_amount": discount_amount,
            "discounted_price": max(0.0, course_price - discount_amount),
        }

    raise HTTPException(status_code=404, detail="Invalid coupon or referral code")
