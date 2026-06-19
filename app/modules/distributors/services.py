"""Distributors module — service layer."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.distributors.models import Distributor, StudentReferral
from app.modules.courses.models import CourseEnrollment
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


async def get_distributor_stats(db: AsyncSession, distributor_id: int) -> dict:
    """Compute stats for a distributor: students referred, courses purchased, revenue."""
    # Total unique students referred
    students_count = (
        await db.execute(
            select(func.count(func.distinct(StudentReferral.student_id)))
            .where(StudentReferral.distributor_id == distributor_id)
        )
    ).scalar() or 0

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
