"""Distributors module — API routes (distributor role)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.distributors import schemas, services

router = APIRouter(prefix="/distributor", tags=["Distributor"])


@router.post("/referral-leads", response_model=schemas.ReferralLeadResponse, status_code=201)
async def create_referral_lead(
    body: schemas.ReferralLeadCreate,
    db: AsyncSession = Depends(get_db),
):
    """Capture a lead when someone opens an IB referral link."""
    lead = await services.create_referral_lead(db, body.model_dump())
    await db.commit()
    return schemas.ReferralLeadResponse.model_validate(lead)


@router.post("/self-register", response_model=schemas.DistributorSelfRegisterResponse, status_code=201)
async def self_register_distributor(
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    city: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    region: str = Form(...),
    bank_account_holder_name: str = Form(...),
    bank_name: str = Form(...),
    bank_account_number: str = Form(...),
    bank_ifsc_code: str = Form(...),
    bank_upi_id: Optional[str] = Form(None),
    profile_photo: Optional[UploadFile] = File(None),
    aadhaar_card: Optional[UploadFile] = File(None),
    pan_card: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Public affiliate IB self-registration form."""
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Password and confirm password do not match")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not profile_photo or not aadhaar_card or not pan_card:
        raise HTTPException(status_code=400, detail="Profile photo, Aadhaar card, and PAN card are required")

    profile_photo_url = await services.save_ib_upload(profile_photo) if profile_photo else None
    aadhaar_card_url = await services.save_ib_upload(aadhaar_card) if aadhaar_card else None
    pan_card_url = await services.save_ib_upload(pan_card) if pan_card else None

    distributor = await services.self_register_distributor(
        db,
        email=email,
        full_name=full_name,
        password=password,
        phone=phone,
        city=city,
        region=region,
        bank_account_holder_name=bank_account_holder_name,
        bank_name=bank_name,
        bank_account_number=bank_account_number,
        bank_ifsc_code=bank_ifsc_code,
        bank_upi_id=bank_upi_id,
        profile_photo_url=profile_photo_url,
        aadhaar_card_url=aadhaar_card_url,
        pan_card_url=pan_card_url,
    )
    await db.commit()
    return schemas.DistributorSelfRegisterResponse(
        message="IB account created successfully. SuperAdmin can review the submitted details.",
        referral_code=distributor.referral_code,
        verification_status=distributor.verification_status,
    )


@router.get("/profile", response_model=schemas.DistributorProfileResponse)
async def get_profile(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    """Get the current distributor's profile."""
    dist = await services.get_distributor_by_user_id(db, current_user.id)
    return schemas.DistributorProfileResponse(
        id=dist.id,
        user_id=dist.user_id,
        region=dist.region,
        referral_code=dist.referral_code,
        discount_percentage=dist.discount_percentage,
        created_at=dist.created_at,
        user_name=dist.user.full_name if dist.user else None,
        user_email=dist.user.email if dist.user else None,
        profile_photo_url=dist.profile_photo_url,
        aadhaar_card_url=dist.aadhaar_card_url,
        pan_card_url=dist.pan_card_url,
        bank_account_holder_name=dist.bank_account_holder_name,
        bank_name=dist.bank_name,
        bank_account_number=dist.bank_account_number,
        bank_ifsc_code=dist.bank_ifsc_code,
        bank_upi_id=dist.bank_upi_id,
        self_registered=dist.self_registered,
        verification_status=dist.verification_status,
    )


@router.get("/referral-code", response_model=schemas.ReferralCodeResponse)
async def get_referral_code(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    """Get the distributor's referral code and discount info."""
    dist = await services.get_distributor_by_user_id(db, current_user.id)
    return schemas.ReferralCodeResponse(
        referral_code=dist.referral_code,
        discount_percentage=dist.discount_percentage,
        region=dist.region,
    )


@router.get("/referrals", response_model=List[schemas.ReferralResponse])
async def get_referrals(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    """List all students referred by this distributor."""
    dist = await services.get_distributor_by_user_id(db, current_user.id)
    return [schemas.ReferralResponse(**row) for row in await services.list_referral_journeys(db, dist.id)]


@router.get("/stats", response_model=schemas.DistributorStatsResponse)
async def get_stats(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    """Get referral statistics for this distributor."""
    dist = await services.get_distributor_by_user_id(db, current_user.id)
    stats = await services.get_distributor_stats(db, dist.id)
    stats["region"] = dist.region
    stats["referral_code"] = dist.referral_code
    return schemas.DistributorStatsResponse(**stats)
