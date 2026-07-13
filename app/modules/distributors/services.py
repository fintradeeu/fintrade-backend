"""Distributors module — service layer."""

import os
import random
import string
from uuid import uuid4
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.auth.services import get_or_create_role
from app.modules.distributors.models import Distributor, ReferralLead, StudentReferral
from app.modules.courses.models import Course, CourseEnrollment
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_distributor_by_user_id(db: AsyncSession, user_id: int) -> Distributor:
    """Get the distributor profile for a given user."""
    result = await db.execute(
        select(Distributor)
        .options(selectinload(Distributor.user))
        .where(Distributor.user_id == user_id)
    )
    distributor = result.scalar_one_or_none()
    if distributor is None:
        raise HTTPException(status_code=404, detail="Distributor profile not found")
    return distributor


async def get_distributor_by_referral_code(db: AsyncSession, code: str) -> Optional[Distributor]:
    """Look up a distributor by referral code."""
    result = await db.execute(
        select(Distributor).where(Distributor.referral_code == code)
    )
    return result.scalar_one_or_none()


async def _generate_referral_code(db: AsyncSession) -> str:
    while True:
        code_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        referral_code = f"IB-{code_suffix}"
        existing = await db.execute(select(Distributor).where(Distributor.referral_code == referral_code))
        if not existing.scalar_one_or_none():
            return referral_code


async def save_ib_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    allowed = {"jpg", "jpeg", "png", "pdf", "webp"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}",
        )
    upload_dir = os.path.join("uploads", "ib-documents")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as out:
        out.write(content)
    return f"/{path.replace(os.sep, '/')}"


async def self_register_distributor(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    password: str,
    phone: Optional[str],
    city: Optional[str],
    region: str,
    bank_account_holder_name: Optional[str],
    bank_name: Optional[str],
    bank_account_number: Optional[str],
    bank_ifsc_code: Optional[str],
    bank_upi_id: Optional[str],
    profile_photo_url: Optional[str],
    aadhaar_card_url: Optional[str],
    pan_card_url: Optional[str],
    franchise_ref: Optional[str] = None,
) -> Distributor:
    existing = await db.execute(select(User).where(User.email == email.strip().lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    role = await get_or_create_role(db, "distributor")
    user = User(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        phone=phone,
        city=city,
        hashed_password=hash_password(password),
        is_verified=True,
        is_active=True,
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    
    franchise_id = None
    if franchise_ref:
        from app.modules.franchise_ibs.models import FranchiseIB
        f_res = await db.execute(select(FranchiseIB).where(FranchiseIB.referral_code == franchise_ref.strip()))
        franchise = f_res.scalar_one_or_none()
        if franchise:
            franchise_id = franchise.id

    distributor = Distributor(
        user_id=user.id,
        franchise_id=franchise_id,
        region=region,
        referral_code=await _generate_referral_code(db),
        discount_percentage=10,
        profile_photo_url=profile_photo_url,
        aadhaar_card_url=aadhaar_card_url,
        pan_card_url=pan_card_url,
        bank_account_holder_name=bank_account_holder_name,
        bank_name=bank_name,
        bank_account_number=bank_account_number,
        bank_ifsc_code=bank_ifsc_code,
        bank_upi_id=bank_upi_id,
        self_registered="yes",
        verification_status="pending",
    )
    db.add(distributor)
    await db.flush()
    await db.refresh(distributor)
    logger.info("distributor_self_registered", distributor_id=distributor.id, referral_code=distributor.referral_code)
    return distributor


async def create_referral_lead(db: AsyncSession, data: dict) -> ReferralLead:
    """Capture a lead before the referred student reaches registration."""
    referral_code = data["referral_code"].strip()
    distributor = await get_distributor_by_referral_code(db, referral_code)
    if distributor is None:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    email = data["email"].strip().lower()
    mobile_no = data["mobile_no"].strip()
    lead_result = await db.execute(
        select(ReferralLead)
        .where(
            ReferralLead.distributor_id == distributor.id,
            ReferralLead.email == email,
        )
        .order_by(ReferralLead.created_at.desc())
    )
    lead = lead_result.scalars().first()
    if lead is None:
        lead = ReferralLead(distributor_id=distributor.id, referral_code=referral_code)
        db.add(lead)

    lead.full_name = data["full_name"].strip()
    lead.email = email
    lead.mobile_no = mobile_no
    lead.city = data.get("city")

    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if user:
        lead.user_id = user.id

    await db.flush()
    await db.refresh(lead)
    logger.info("referral_lead_captured", lead_id=lead.id, distributor_id=distributor.id)
    return lead


async def link_referral_lead_to_user(db: AsyncSession, distributor_id: int, user: User) -> None:
    """Attach an existing captured lead to the registered user."""
    phone = (user.phone or "").strip()
    result = await db.execute(
        select(ReferralLead)
        .where(
            ReferralLead.distributor_id == distributor_id,
            ReferralLead.user_id.is_(None),
            (ReferralLead.email == user.email) | (ReferralLead.mobile_no == phone),
        )
        .order_by(ReferralLead.created_at.desc())
    )
    lead = result.scalars().first()
    if lead:
        lead.user_id = user.id
        await db.flush()


async def list_referrals(db: AsyncSession, distributor_id: Optional[int] = None, franchise_ib_id: Optional[int] = None) -> List[StudentReferral]:
    """List referrals for a distributor or franchise IB, hiding stale pending rows after enrollment."""
    stmt = select(StudentReferral).options(
        selectinload(StudentReferral.student),
        selectinload(StudentReferral.course),
    ).order_by(StudentReferral.created_at.desc())
    
    if distributor_id:
        stmt = stmt.where(StudentReferral.distributor_id == distributor_id)
    elif franchise_ib_id:
        stmt = stmt.outerjoin(Distributor, Distributor.id == StudentReferral.distributor_id).where(
            (StudentReferral.franchise_ib_id == franchise_ib_id) | (Distributor.franchise_id == franchise_ib_id)
        )
        
    result = await db.execute(stmt)
    referrals = list(result.scalars().all())

    enrolled_stmt = select(CourseEnrollment.user_id).where(CourseEnrollment.is_active == True) # noqa: E712
    if distributor_id:
        enrolled_stmt = enrolled_stmt.where(CourseEnrollment.distributor_id == distributor_id)
    # Note: For franchise IB, we could check enrollment through their IBs, but simplified for now:
    enrolled_students_result = await db.execute(enrolled_stmt.distinct())
    enrolled_student_ids = set(enrolled_students_result.scalars().all())

    return [
        referral
        for referral in referrals
        if not (referral.course_id is None and referral.student_id in enrolled_student_ids)
    ]


async def list_referral_journeys(db: AsyncSession, distributor_id: Optional[int] = None, franchise_ib_id: Optional[int] = None) -> list[dict]:
    """Return captured leads and registered referrals with student journey status."""
    from app.modules.exams.models import EntranceExam, ExamResult
    from app.modules.kyc.models import KYCSubmission

    stmt = select(ReferralLead).options(selectinload(ReferralLead.user)).order_by(ReferralLead.created_at.desc())
    if distributor_id:
        stmt = stmt.where(ReferralLead.distributor_id == distributor_id)
    elif franchise_ib_id:
        # Leads via sub-IBs
        stmt = stmt.join(Distributor, Distributor.id == ReferralLead.distributor_id).where(Distributor.franchise_id == franchise_ib_id)
        
    leads_result = await db.execute(stmt)
    leads = list(leads_result.scalars().all())

    referrals = await list_referrals(db, distributor_id=distributor_id, franchise_ib_id=franchise_ib_id)
    rows_by_key: dict[str, dict] = {}

    for lead in leads:
        key = str(lead.user_id) if lead.user_id else f"lead:{lead.id}"
        rows_by_key[key] = {
            "id": lead.id,
            "lead_id": lead.id,
            "student_id": lead.user_id,
            "student_name": lead.user.full_name if lead.user else lead.full_name,
            "student_email": lead.user.email if lead.user else lead.email,
            "mobile_no": lead.user.phone if lead.user and lead.user.phone else lead.mobile_no,
            "city": lead.user.city if lead.user and lead.user.city else lead.city,
            "course_id": None,
            "course_title": None,
            "created_at": lead.created_at,
        }

    for referral in referrals:
        key = str(referral.student_id)
        if key not in rows_by_key:
            rows_by_key[key] = {
                "id": referral.id,
                "lead_id": None,
                "student_id": referral.student_id,
                "student_name": referral.student.full_name if referral.student else None,
                "student_email": referral.student.email if referral.student else None,
                "mobile_no": referral.student.phone if referral.student else None,
                "city": referral.student.city if referral.student else None,
                "course_id": referral.course_id,
                "course_title": referral.course.title if referral.course else None,
                "created_at": referral.created_at,
            }
        elif referral.course and not rows_by_key[key].get("course_title"):
            rows_by_key[key]["course_id"] = referral.course_id
            rows_by_key[key]["course_title"] = referral.course.title

    user_ids = [row["student_id"] for row in rows_by_key.values() if row.get("student_id")]
    if not user_ids:
        return [_journey_defaults(row) for row in rows_by_key.values()]

    enrollments_result = await db.execute(
        select(CourseEnrollment, Course)
        .join(Course, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id.in_(user_ids))
    )
    enrollments_by_user: dict[int, list[tuple[CourseEnrollment, Course]]] = {}
    for enrollment, course in enrollments_result.all():
        enrollments_by_user.setdefault(enrollment.user_id, []).append((enrollment, course))

    kyc_result = await db.execute(select(KYCSubmission).where(KYCSubmission.user_id.in_(user_ids)))
    kyc_by_user = {kyc.user_id: kyc for kyc in kyc_result.scalars().all()}

    exam_result = await db.execute(
        select(ExamResult, EntranceExam, Course)
        .join(EntranceExam, ExamResult.exam_id == EntranceExam.id)
        .join(Course, EntranceExam.course_id == Course.id)
        .where(ExamResult.user_id.in_(user_ids))
        .order_by(ExamResult.evaluated_at.desc())
    )
    exam_by_user: dict[int, tuple[ExamResult, EntranceExam, Course]] = {}
    for result, exam, course in exam_result.all():
        exam_by_user.setdefault(result.user_id, (result, exam, course))

    output = []
    for row in rows_by_key.values():
        user_id = row.get("student_id")
        row = _journey_defaults(row)
        row["registered"] = bool(user_id)
        if user_id:
            enrollments = enrollments_by_user.get(user_id, [])
            row["enrolled"] = bool(enrollments)
            row["fees_paid"] = any((en.price_paid or 0) > 0 for en, _course in enrollments)
            row["enrolled_courses"] = [course.title for _en, course in enrollments]
            row["course_completed"] = any((en.progress_percent or 0) >= 100 for en, _course in enrollments)
            if enrollments and not row.get("course_title"):
                row["course_id"] = enrollments[0][0].course_id
                row["course_title"] = enrollments[0][1].title

            kyc = kyc_by_user.get(user_id)
            row["kyc_done"] = bool(kyc)
            row["kyc_status"] = kyc.status if kyc else None

            exam_info = exam_by_user.get(user_id)
            if exam_info:
                result, _exam, course = exam_info
                row["entrance_exam_given"] = True
                row["entrance_exam_course_title"] = course.title
                row["entrance_exam_score"] = float(result.percentage or 0)
                row["entrance_exam_passed"] = bool(result.passed)

        output.append(row)

    return sorted(output, key=lambda item: item["created_at"], reverse=True)


def _journey_defaults(row: dict) -> dict:
    row.setdefault("registered", False)
    row.setdefault("entrance_exam_given", False)
    row.setdefault("entrance_exam_course_title", None)
    row.setdefault("entrance_exam_score", None)
    row.setdefault("entrance_exam_passed", None)
    row.setdefault("kyc_done", False)
    row.setdefault("kyc_status", None)
    row.setdefault("enrolled", False)
    row.setdefault("fees_paid", False)
    row.setdefault("enrolled_courses", [])
    row.setdefault("course_completed", False)
    return row


async def get_distributor_stats(db: AsyncSession, distributor_id: int) -> dict:
    """Compute stats for a distributor: students referred, courses purchased, revenue."""
    # Total unique registered students plus captured pre-registration leads.
    registered_students_count = (
        await db.execute(
            select(func.count(func.distinct(StudentReferral.student_id)))
            .where(StudentReferral.distributor_id == distributor_id)
        )
    ).scalar() or 0
    unregistered_leads_count = (
        await db.execute(
            select(func.count(ReferralLead.id))
            .where(
                ReferralLead.distributor_id == distributor_id,
                ReferralLead.user_id.is_(None),
            )
        )
    ).scalar() or 0
    students_count = registered_students_count + unregistered_leads_count

    # Total successfully enrolled courses through this distributor
    courses_count = (
        await db.execute(
            select(func.count(CourseEnrollment.id))
            .where(
                CourseEnrollment.distributor_id == distributor_id,
                CourseEnrollment.is_active == True,  # noqa: E712
            )
        )
    ).scalar() or 0

    # Total revenue from enrollments via this distributor
    revenue = (
        await db.execute(
            select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
            .where(CourseEnrollment.distributor_id == distributor_id)
        )
    ).scalar() or 0.0

    return {
        "distributor_id": distributor_id,
        "total_students_referred": students_count,
        "total_courses_purchased": courses_count,
        "total_revenue_generated": float(revenue),
    }


async def list_all_distributors(db: AsyncSession) -> List[Distributor]:
    """List all distributors (admin use)."""
    result = await db.execute(
        select(Distributor)
        .options(selectinload(Distributor.user))
        .order_by(Distributor.created_at.desc())
    )
    return list(result.scalars().all())


async def manual_register_student(
    db: AsyncSession,
    data: schemas.ManualStudentRegisterRequest,
    distributor_id: Optional[int] = None,
    franchise_ib_id: Optional[int] = None,
) -> dict:
    """Manually register a student by an IB or Franchise IB."""
    from app.modules.auth.models import User
    from app.modules.auth.services import register_user
    from app.modules.payments.services import create_offline_payment
    from app.modules.payments.schemas import OfflinePaymentRequest
    from app.utils.smtp_notifications import send_email
    
    # 1. Generate random password
    password = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    
    # 2. Check if user exists. If yes, we don't recreate them, but we still assign referral if not already assigned
    existing = await db.execute(select(User).where(User.email == data.email.strip().lower()))
    user = existing.scalar_one_or_none()
    
    is_new_user = False
    if not user:
        # We need to register the user
        user = await register_user(
            db=db,
            email=data.email,
            full_name=data.full_name,
            password=password,
            phone=data.phone,
            city=data.city,
            role_name="student",
        )
        is_new_user = True
        
    # 3. Add StudentReferral
    existing_ref = await db.execute(
        select(StudentReferral).where(StudentReferral.student_id == user.id)
    )
    if not existing_ref.scalar_one_or_none():
        referral = StudentReferral(
            student_id=user.id,
            distributor_id=distributor_id,
            franchise_ib_id=franchise_ib_id,
            course_id=data.course_id,
        )
        db.add(referral)
        await db.flush()
        
    # 4. Handle Offline Payment if course_id is provided and payment_mode is offline
    payment_response = None
    if data.course_id and data.payment_mode in ["cash", "cheque"]:
        payment_req = OfflinePaymentRequest(
            course_id=data.course_id,
            payment_mode=data.payment_mode,
            amount=data.amount,
            reference_number=data.reference_number,
            cheque_image_url=data.cheque_image_url,
            remarks=data.remarks,
        )
        payment_response = await create_offline_payment(db, user, payment_req)
        
    await db.commit()
    
    # 5. Send Email to Student with credentials if new user
    if is_new_user:
        frontend_url = settings.CORS_ORIGINS.split(',')[0] if settings.CORS_ORIGINS else "https://fintrade.com"
        email_html = f"""
        <html>
            <body>
                <h2>Welcome to FinTrade, {user.full_name}!</h2>
                <p>An account has been created for you by your IB.</p>
                <p><strong>Username/Email:</strong> {user.email}</p>
                <p><strong>Password:</strong> {password}</p>
                <p>You can login at: <a href="{frontend_url}/login">{frontend_url}/login</a></p>
                <p>Please change your password after logging in.</p>
            </body>
        </html>
        """
        try:
            await send_email(
                to_email=user.email,
                subject="Welcome to FinTrade - Your Account Details",
                body_html=email_html
            )
        except Exception as e:
            logger.error("manual_registration_email_failed", error=str(e))
            
    return {
        "status": "success",
        "message": "Student registered successfully.",
        "user_id": user.id,
        "payment_info": payment_response,
    }
