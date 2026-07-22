"""KYC module — business logic / services."""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import HTTPException, UploadFile
# pyrefly: ignore [missing-import]
from sqlalchemy import select
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import selectinload

from app.modules.kyc.models import KYCSubmission, Contract

# ── Student services ────────────────────────────────────────────────

async def submit_kyc(db: AsyncSession, user_id: int, data: dict) -> KYCSubmission:
    """Create or update KYC submission for a user."""
    from app.modules.auth.models import User
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user and user.phone:
        data["mobile"] = user.phone

    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()

    if kyc:
        # A rejected submission becomes a fresh pending review as soon as the
        # student starts filling it again.
        if kyc.status == "rejected":
            kyc.status = "pending"
            kyc.rejection_reason = None
            kyc.reviewed_by = None
            kyc.reviewed_at = None
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


from datetime import timedelta

async def send_mobile_otp(db: AsyncSession, user_id: int) -> bool:
    """Send an SMS OTP using Twilio Verify or Fast2SMS to the user's KYC mobile number."""
    from app.modules.auth.models import User
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.phone:
        raise HTTPException(
            status_code=400,
            detail="User or phone number not found. Please update your profile first."
        )

    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if kyc and kyc.mobile != user.phone:
        kyc.mobile = user.phone
        await db.commit()
    
    from app.modules.auth.services import _generate_otp_code, _generate_otp_token
    from app.modules.auth.models import OTPCode
    from app.config import settings

    otp_token = _generate_otp_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    
    from app.core.twilio_otp import is_local_sms_otp_enabled, send_sms_otp

    if is_local_sms_otp_enabled():
        code = _generate_otp_code()
    else:
        code = "000000"  # Placeholder code in DB for Twilio Verify (code is managed by Twilio)

    # Store code in database
    otp = OTPCode(
        user_id=user_id,
        code=code,
        otp_token=otp_token,
        channel="sms",
        expires_at=expires_at,
    )
    db.add(otp)
    await db.commit()

    sent = False
    try:
        sent = await send_sms_otp(kyc.mobile, code)
    except Exception as e:
        from app.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error("kyc_mobile_otp_sending_failed", error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to send SMS OTP: {str(e)}"
        )

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Failed to send SMS OTP. Please check the Nimbus SMS gateway response in backend logs."
        )

    return True


async def send_email_otp(db: AsyncSession, user) -> bool:
    """Generate and send an email OTP via SMTP for KYC email verification."""
    from app.modules.auth.services import _generate_otp_code, _generate_otp_token
    from app.modules.auth.models import OTPCode
    from app.config import settings
    from app.utils.smtp_notifications import build_otp_email_html, send_email

    otp_token = _generate_otp_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    code = _generate_otp_code()

    # Store code in database
    otp = OTPCode(
        user_id=user.id,
        code=code,
        otp_token=otp_token,
        channel="email",
        expires_at=expires_at,
    )
    db.add(otp)
    await db.commit()

    print(f"\n🔑 [KYC OTP SERVICE] Generated Email OTP code: {code} for user: {user.email}\n", flush=True)

    email_html = build_otp_email_html(code, user.full_name)
    email_sent = await send_email(
        to_email=user.email,
        subject=f"{code} — Your FinTrade KYC Verification Code",
        body_html=email_html,
    )
    if not email_sent:
        # Development bypass if SMTP is not configured
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            print(f"\n⚠️ [KYC OTP SERVICE - DEVELOPMENT ONLY] SMTP is not configured. Verification code is {code} (Token: {otp_token})\n", flush=True)
            return True
        raise HTTPException(status_code=500, detail="Failed to send verification email.")
    return True


async def verify_otp(db: AsyncSession, user_id: int, otp_type: str, otp: str) -> KYCSubmission:
    """Verify mobile or email OTP (mobile verified with '123456' mock fallback, email matches SMTP OTP)."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found. Submit personal details first.")

    if otp_type == "mobile":
        from app.modules.auth.models import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.phone:
            raise HTTPException(status_code=400, detail="No mobile number registered for verification.")
        
        if kyc.mobile != user.phone:
            kyc.mobile = user.phone
            await db.commit()
        
        is_valid = False
        from app.core.twilio_otp import is_local_sms_otp_enabled

        if is_local_sms_otp_enabled():
            # Look up the latest unused SMS OTP code
            from app.modules.auth.models import OTPCode
            # pyrefly: ignore [missing-import]
            from sqlalchemy import desc

            result = await db.execute(
                select(OTPCode)
                .where(
                    OTPCode.user_id == user_id,
                    OTPCode.channel == "sms",
                    OTPCode.is_used == False
                )
                .order_by(desc(OTPCode.created_at))
            )
            otp_record = result.scalars().first()
            if not otp_record:
                raise HTTPException(status_code=400, detail="No active mobile OTP verification found.")

            if otp_record.expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

            if otp_record.code != otp.strip():
                otp_record.attempts += 1
                await db.commit()
                raise HTTPException(status_code=400, detail="Incorrect verification code.")

            otp_record.is_used = True
            is_valid = True
        else:
            try:
                from app.core.twilio_otp import check_twilio_otp
                is_valid = await check_twilio_otp(kyc.mobile, otp)
            except Exception:
                is_valid = False


        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid or expired mobile OTP.")
        
        kyc.mobile_verified = True
    elif otp_type == "email":
        from app.modules.auth.models import OTPCode
        # pyrefly: ignore [missing-import]
        from sqlalchemy import desc

        # Look up the latest unused email OTP code
        result = await db.execute(
            select(OTPCode)
            .where(
                OTPCode.user_id == user_id,
                OTPCode.channel == "email",
                OTPCode.is_used == False
            )
            .order_by(desc(OTPCode.created_at))
        )
        otp_record = result.scalars().first()
        if not otp_record:
            raise HTTPException(status_code=400, detail="No active email OTP verification found.")

        if otp_record.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

        if otp_record.code != otp.strip():
            otp_record.attempts += 1
            await db.commit()
            raise HTTPException(status_code=400, detail="Incorrect verification code.")

        otp_record.is_used = True
        kyc.email_verified = True
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP type")

    await db.commit()
    await db.refresh(kyc)
    return kyc


async def _resolve_or_create_student_user(db: AsyncSession, user_id: int, fallback_name: str = "", fallback_mobile: str = ""):
    """Resolve a User by id or lead id, creating a student User account if needed."""
    from app.modules.auth.models import User
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if user:
        return user

    from app.modules.distributors.models import ReferralLead
    lead_res = await db.execute(select(ReferralLead).where(ReferralLead.id == user_id))
    lead = lead_res.scalar_one_or_none()

    if lead and lead.user_id:
        u_res = await db.execute(select(User).where(User.id == lead.user_id))
        user = u_res.scalar_one_or_none()
        if user:
            return user

    full_name = fallback_name or (lead.full_name if lead else f"Student #{user_id}")
    user_email = (lead.email if (lead and lead.email) else f"student_{user_id}@fintrade.com").lower().strip()
    user_phone = fallback_mobile or (lead.mobile_no if lead else "")

    ex_user = (await db.execute(select(User).where(User.email == user_email))).scalar_one_or_none()
    if ex_user:
        if lead:
            lead.user_id = ex_user.id
            await db.commit()
        return ex_user

    from app.modules.auth.services import get_password_hash
    user = User(
        email=user_email,
        hashed_password=get_password_hash("Student@123"),
        full_name=full_name,
        phone=user_phone,
        city=lead.city if lead else "",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    from app.modules.roles.models import Role, UserRole
    st_role = (await db.execute(select(Role).where(Role.name == "student"))).scalar_one_or_none()
    if st_role:
        db.add(UserRole(user_id=user.id, role_id=st_role.id))
        await db.commit()

    if lead:
        lead.user_id = user.id
        await db.commit()

    return user


async def upload_document(
    db: AsyncSession, user_id: int, doc_type: str, file: UploadFile
) -> KYCSubmission:
    """Upload a KYC document (aadhaar, pan, photo, signature, biometric)."""
    user = await _resolve_or_create_student_user(db, user_id)
    user_id = user.id

    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        kyc = KYCSubmission(
            user_id=user_id,
            full_name=user.full_name,
            mobile=user.phone if user.phone else "0000000000",
            status="pending",
        )
        db.add(kyc)
        await db.commit()
        await db.refresh(kyc)

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
    """Complete KYC and create the contract dossier for optional admin review."""
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == user_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    from app.modules.auth.models import User
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user and user.phone and kyc.mobile != user.phone:
        kyc.mobile = user.phone
        await db.commit()

    required_documents = (
        kyc.aadhaar_doc_url,
        kyc.pan_doc_url,
        kyc.photo_url,
        kyc.signature_url,
        kyc.biometric_selfie_url,
    )
    if not all(required_documents):
        raise HTTPException(status_code=400, detail="Upload all KYC documents before submitting for review")
    if kyc.status == "rejected":
        raise HTTPException(status_code=400, detail="Please fill and upload all documents again")

    if kyc.status != "verified":
        kyc.status = "verified"
        kyc.rejection_reason = None
        kyc.reviewed_by = None
        kyc.reviewed_at = None
        await db.flush()

    # Check if a contract already exists for this user (one-time contract)
    existing_result = await db.execute(
        select(Contract).where(Contract.user_id == user_id).order_by(Contract.created_at.desc())
    )
    existing_contract = existing_result.scalar_one_or_none()
    if existing_contract:
        if course_id is not None:
            existing_contract.course_id = course_id
        if terms_accepted:
            existing_contract.terms_accepted = True
            existing_contract.signed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing_contract)
        return existing_contract

    # Generate contract number (with collision avoidance)
    count_result = await db.execute(select(Contract))
    total = len(count_result.scalars().all())
    year = datetime.now().year
    counter = total + 1
    while True:
        contract_number = f"FT-{year}-{str(counter).zfill(3)}"
        existing = await db.execute(
            select(Contract).where(Contract.contract_number == contract_number)
        )
        if existing.scalar_one_or_none() is None:
            break
        counter += 1

    contract_text = f"""
FINTRADE TRADING EDUCATION AGREEMENT
======================================
Contract ID    : {contract_number}
Student Name   : {kyc.full_name}
Mobile         : {kyc.mobile or 'N/A'}
Aadhaar        : {kyc.aadhaar_number or 'N/A'}
PAN            : {kyc.pan_number or 'N/A'}

KYC Status     : COMPLETED
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
        signed_at=datetime.now(timezone.utc) if terms_accepted else None,
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
    placeholder_img = "/uploads/kyc/admin_verified.png"
    if not kyc.aadhaar_doc_url: kyc.aadhaar_doc_url = placeholder_img
    if not kyc.pan_doc_url: kyc.pan_doc_url = placeholder_img
    if not kyc.photo_url: kyc.photo_url = placeholder_img
    if not kyc.signature_url: kyc.signature_url = placeholder_img
    if not kyc.biometric_selfie_url: kyc.biometric_selfie_url = placeholder_img

    kyc.status = "verified"
    kyc.mobile_verified = True
    kyc.email_verified = True
    kyc.reviewed_by = admin_id
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.rejection_reason = None
    await db.commit()
    await db.refresh(kyc)
    return kyc


async def direct_complete_kyc(db: AsyncSession, admin_id: int, data: dict) -> KYCSubmission:
    """Directly perform and complete eKYC for any student from SuperAdmin panel."""
    user_id = data["user_id"]
    user = await _resolve_or_create_student_user(db, user_id, fallback_name=data.get("full_name") or "", fallback_mobile=data.get("mobile") or "")
    user_id = user.id

    full_name = data.get("full_name") or user.full_name or "Student"
    mobile = data.get("mobile") or user.phone or ""

    # Check if KYC submission exists
    res = await db.execute(select(KYCSubmission).where(KYCSubmission.user_id == user_id))
    kyc = res.scalar_one_or_none()

    placeholder_img = "/uploads/kyc/admin_verified.png"

    if not kyc:
        kyc = KYCSubmission(
            user_id=user_id,
            full_name=full_name,
            dob=data.get("dob"),
            qualification=data.get("qualification"),
            address=data.get("address"),
            mobile=mobile,
            aadhaar_number=data.get("aadhaar_number"),
            pan_number=data.get("pan_number"),
            aadhaar_doc_url=data.get("aadhaar_doc_url") or placeholder_img,
            pan_doc_url=data.get("pan_doc_url") or placeholder_img,
            photo_url=data.get("photo_url") or placeholder_img,
            signature_url=data.get("signature_url") or placeholder_img,
            biometric_selfie_url=data.get("biometric_selfie_url") or placeholder_img,
            mobile_verified=True,
            email_verified=True,
            status="verified" if data.get("mark_verified", True) else "pending",
            reviewed_by=admin_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(kyc)
    else:
        kyc.full_name = full_name
        if data.get("dob"): kyc.dob = data.get("dob")
        if data.get("qualification"): kyc.qualification = data.get("qualification")
        if data.get("address"): kyc.address = data.get("address")
        if mobile: kyc.mobile = mobile
        if data.get("aadhaar_number"): kyc.aadhaar_number = data.get("aadhaar_number")
        if data.get("pan_number"): kyc.pan_number = data.get("pan_number")

        kyc.aadhaar_doc_url = data.get("aadhaar_doc_url") or kyc.aadhaar_doc_url or placeholder_img
        kyc.pan_doc_url = data.get("pan_doc_url") or kyc.pan_doc_url or placeholder_img
        kyc.photo_url = data.get("photo_url") or kyc.photo_url or placeholder_img
        kyc.signature_url = data.get("signature_url") or kyc.signature_url or placeholder_img
        kyc.biometric_selfie_url = data.get("biometric_selfie_url") or kyc.biometric_selfie_url or placeholder_img

        kyc.mobile_verified = True
        kyc.email_verified = True
        if data.get("mark_verified", True):
            kyc.status = "verified"
        kyc.reviewed_by = admin_id
        kyc.reviewed_at = datetime.now(timezone.utc)
        kyc.rejection_reason = None

    await db.commit()
    await db.refresh(kyc)

    if data.get("generate_contract", True):
        course_id = data.get("course_id")
        await generate_contract(db, user_id, course_id=course_id, terms_accepted=True)

    return kyc


async def reject_kyc(db: AsyncSession, kyc_id: int, admin_id: int, reason: str) -> KYCSubmission:
    """Reject a KYC submission with reason."""
    kyc = await get_kyc_detail(db, kyc_id)
    reason = reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    kyc.status = "rejected"
    kyc.reviewed_by = admin_id
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.rejection_reason = reason
    # Force a complete fresh upload. Old files remain on disk for audit/cleanup,
    # but are no longer attached to the active submission.
    kyc.aadhaar_doc_url = None
    kyc.pan_doc_url = None
    kyc.photo_url = None
    kyc.signature_url = None
    kyc.biometric_selfie_url = None
    await db.commit()
    await db.refresh(kyc)
    return kyc


async def list_contracts(db: AsyncSession, skip: int = 0, limit: int = 50):
    """List all contracts (admin)."""
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.user))
        .order_by(Contract.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_contract_detail(db: AsyncSession, contract_id: int) -> Contract:
    """Get a specific contract by ID."""
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.user))
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract
