"""Distributors module — service layer."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
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


async def list_referrals(db: AsyncSession, distributor_id: int) -> List[StudentReferral]:
    """List referrals for a distributor, hiding stale pending rows after enrollment."""
    result = await db.execute(
        select(StudentReferral)
        .options(
            selectinload(StudentReferral.student),
            selectinload(StudentReferral.course),
        )
        .where(StudentReferral.distributor_id == distributor_id)
        .order_by(StudentReferral.created_at.desc())
    )
    referrals = list(result.scalars().all())

    enrolled_students_result = await db.execute(
        select(CourseEnrollment.user_id)
        .where(
            CourseEnrollment.distributor_id == distributor_id,
            CourseEnrollment.is_active == True,  # noqa: E712
        )
        .distinct()
    )
    enrolled_student_ids = set(enrolled_students_result.scalars().all())

    return [
        referral
        for referral in referrals
        if not (referral.course_id is None and referral.student_id in enrolled_student_ids)
    ]


async def list_referral_journeys(db: AsyncSession, distributor_id: int) -> list[dict]:
    """Return captured leads and registered referrals with student journey status."""
    from app.modules.exams.models import EntranceExam, ExamResult
    from app.modules.kyc.models import KYCSubmission

    leads_result = await db.execute(
        select(ReferralLead)
        .options(selectinload(ReferralLead.user))
        .where(ReferralLead.distributor_id == distributor_id)
        .order_by(ReferralLead.created_at.desc())
    )
    leads = list(leads_result.scalars().all())

    referrals = await list_referrals(db, distributor_id)
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
