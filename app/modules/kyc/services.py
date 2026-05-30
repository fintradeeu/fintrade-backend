"""KYC module — business logic / services."""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.kyc.models import KYCSubmission, Contract


# ── Student services ────────────────────────────────────────────────

async def submit_kyc(db: AsyncSession, user_id: int, data: dict) -> KYCSubmission:
    """Create or update KYC submission for a user."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()

    if kyc:
        for key, value in data.items():
            if value is not None:
                setattr(kyc, key, value)
    else:
        kyc = KYCSubmission(user_id=user_id, **data)
        db.add(kyc)

    await db.commit()
    await db.refresh(kyc)
    return kyc


async def get_kyc_status(db: AsyncSession, user_id: int) -> Optional[KYCSubmission]:
    """Get KYC submission for current user."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def verify_otp(db: AsyncSession, user_id: int, otp_type: str, otp: str) -> KYCSubmission:
    """Verify mobile or email OTP (demo mode — any 6-digit code accepted)."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found. Submit personal details first.")

    # Demo mode: accept any OTP with 4-6 digits
    if len(otp) < 4:
        raise HTTPException(status_code=400, detail="Invalid OTP format")

    if otp_type == "mobile":
        kyc.mobile_verified = True
    elif otp_type == "email":
        kyc.email_verified = True
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP type")

    await db.commit()
    await db.refresh(kyc)
    return kyc


async def upload_document(
    db: AsyncSession, user_id: int, doc_type: str, file: UploadFile
) -> KYCSubmission:
    """Upload a KYC document (aadhaar, pan, photo, signature, biometric)."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found")

    # Save file
    os.makedirs("uploads/kyc", exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{user_id}_{doc_type}_{uuid.uuid4()}{ext}"
    filepath = os.path.join("uploads", "kyc", filename)
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    url = f"/uploads/kyc/{filename}"

    # Map doc_type to model field
    field_map = {
        "aadhaar": "aadhaar_doc_url",
        "pan": "pan_doc_url",
        "photo": "photo_url",
        "signature": "signature_url",
        "biometric": "biometric_selfie_url",
    }
    field = field_map.get(doc_type)
    if not field:
        raise HTTPException(status_code=400, detail=f"Invalid document type: {doc_type}")

    setattr(kyc, field, url)
    await db.commit()
    await db.refresh(kyc)
    return kyc


async def generate_contract(
    db: AsyncSession, user_id: int, course_id: Optional[int], terms_accepted: bool
) -> Contract:
    """Generate a contract after KYC is verified."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    if kyc.status != "verified":
        kyc.status = "verified"
        await db.commit()

    # Generate contract number
    count_result = await db.execute(select(Contract))
    total = len(count_result.scalars().all())
    contract_number = f"FT-{datetime.now().year}-{str(total + 1).zfill(3)}"

    contract_text = f"""
FINTRADE TRADING EDUCATION AGREEMENT
======================================
Contract ID    : {contract_number}
Student Name   : {kyc.full_name}
Mobile         : {kyc.mobile or 'N/A'}
Aadhaar        : {kyc.aadhaar_number or 'N/A'}
PAN            : {kyc.pan_number or 'N/A'}

KYC Status     : VERIFIED
Contract Date  : {datetime.now().strftime('%d %B %Y')}

TERMS & CONDITIONS
------------------
1. The Student agrees to abide by all FinTrade platform rules and community guidelines.
2. Course fees are non-refundable after 7 days of enrollment.
3. All course material is proprietary and may not be shared or redistributed.
4. Trading simulation is for educational purposes only; no real capital is at risk.
5. FinTrade holds the right to revoke access for breach of terms.
6. Placement assistance is merit-based and not guaranteed.
7. This contract is governed by the laws of India.

Signed digitally by: {kyc.full_name}
Date: {datetime.now().strftime('%d/%m/%Y')}

© {datetime.now().year} FinTrade Education Pvt. Ltd. | Mumbai, India
    """.strip()

    contract = Contract(
        user_id=user_id,
        kyc_id=kyc.id,
        contract_number=contract_number,
        course_id=course_id,
        terms_accepted=terms_accepted,
        signed_at=datetime.now(timezone.utc),
        contract_text=contract_text,
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return contract


async def get_user_contract(db: AsyncSession, user_id: int) -> Optional[Contract]:
    """Get the latest contract for a user."""
    result = await db.execute(
        select(Contract).where(Contract.user_id == user_id).order_by(Contract.created_at.desc())
    )
    return result.scalar_one_or_none()


# ── Admin services ──────────────────────────────────────────────────

async def list_kyc_submissions(db: AsyncSession, skip: int = 0, limit: int = 50):
    """List all KYC submissions (admin)."""
    result = await db.execute(
        select(KYCSubmission)
        .order_by(KYCSubmission.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_kyc_detail(db: AsyncSession, kyc_id: int) -> KYCSubmission:
    """Get a specific KYC submission by ID."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.id == kyc_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    return kyc


async def approve_kyc(db: AsyncSession, kyc_id: int, admin_id: int) -> KYCSubmission:
    """Approve a KYC submission."""
    kyc = await get_kyc_detail(db, kyc_id)
    kyc.status = "verified"
    kyc.reviewed_by = admin_id
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.rejection_reason = None
    await db.commit()
    await db.refresh(kyc)
    return kyc


async def reject_kyc(db: AsyncSession, kyc_id: int, admin_id: int, reason: str) -> KYCSubmission:
    """Reject a KYC submission with reason."""
    kyc = await get_kyc_detail(db, kyc_id)
    kyc.status = "rejected"
    kyc.reviewed_by = admin_id
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.rejection_reason = reason
    await db.commit()
    await db.refresh(kyc)
    return kyc


async def list_contracts(db: AsyncSession, skip: int = 0, limit: int = 50):
    """List all contracts (admin)."""
    result = await db.execute(
        select(Contract)
        .order_by(Contract.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_contract_detail(db: AsyncSession, contract_id: int) -> Contract:
    """Get a specific contract by ID."""
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract
