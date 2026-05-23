"""Admin module — service layer."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.modules.auth.models import User, Role
from app.modules.auth.services import get_or_create_role
from app.modules.courses.models import Course, CourseEnrollment
from app.modules.exams.models import EntranceExam
from app.modules.lectures.models import Lecture
from app.modules.distributors.models import Distributor, StudentReferral
from app.modules.offers.models import Offer
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Dashboard ────────────────────────────────────────────────────────
async def get_admin_stats(db: AsyncSession) -> dict:
    """Aggregate dashboard statistics."""
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    courses_count = (await db.execute(select(func.count(Course.id)))).scalar() or 0
    enrollments_count = (await db.execute(select(func.count(CourseEnrollment.id)))).scalar() or 0
    exams_count = (await db.execute(select(func.count(EntranceExam.id)))).scalar() or 0
    lectures_count = (await db.execute(select(func.count(Lecture.id)))).scalar() or 0
    distributors_count = (await db.execute(select(func.count(Distributor.id)))).scalar() or 0

    return {
        "total_users": users_count,
        "total_courses": courses_count,
        "total_enrollments": enrollments_count,
        "total_exams": exams_count,
        "total_lectures": lectures_count,
        "total_distributors": distributors_count,
    }


# ── User listing ─────────────────────────────────────────────────────
async def list_users(db: AsyncSession, skip: int = 0, limit: int = 50) -> dict:
    """List all users for admin dashboard."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())
    total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    return {"users": users, "total": total}


# ── User creation ────────────────────────────────────────────────────
async def create_user_with_role(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: str,
    role_name: str,
    created_by: int,
    phone: Optional[str] = None,
) -> User:
    """Admin creates a user with a specific role."""
    # Check uniqueness
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    role = await get_or_create_role(db, role_name)

    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(password),
        is_verified=True,  # Admin-created accounts are pre-verified
        created_by=created_by,
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    # Eager load the roles to prevent MissingGreenlet error in Pydantic schema validation
    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user.id))
    user = result.scalar_one()
    
    logger.info("admin_created_user", user_id=user.id, role=role_name, created_by=created_by)
    return user


async def create_distributor_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: str,
    region: str,
    referral_code: str,
    discount_percentage: float,
    created_by: int,
    phone: Optional[str] = None,
) -> tuple:
    """Admin creates a distributor: user + distributor profile."""
    # Check referral code uniqueness
    existing_code = await db.execute(
        select(Distributor).where(Distributor.referral_code == referral_code)
    )
    if existing_code.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Referral code already exists",
        )

    user = await create_user_with_role(
        db, email, full_name, password, "distributor", created_by, phone
    )

    distributor = Distributor(
        user_id=user.id,
        region=region,
        referral_code=referral_code,
        discount_percentage=discount_percentage,
    )
    db.add(distributor)
    await db.flush()
    await db.refresh(distributor)
    logger.info("distributor_created", distributor_id=distributor.id, referral_code=referral_code)
    return user, distributor


# ── Distributor management ───────────────────────────────────────────
async def list_distributors(db: AsyncSession):
    """List all distributors with user info."""
    result = await db.execute(
        select(Distributor)
        .options(selectinload(Distributor.user))
        .order_by(Distributor.created_at.desc())
    )
    return list(result.scalars().all())


async def get_distributor_stats(db: AsyncSession, distributor_id: int) -> dict:
    """Get stats for a specific distributor (admin view)."""
    dist = await db.get(Distributor, distributor_id)
    if dist is None:
        raise HTTPException(status_code=404, detail="Distributor not found")

    # Load user for name
    user_result = await db.execute(
        select(User).where(User.id == dist.user_id)
    )
    user = user_result.scalar_one_or_none()

    students_count = (
        await db.execute(
            select(func.count(func.distinct(StudentReferral.student_id)))
            .where(StudentReferral.distributor_id == distributor_id)
        )
    ).scalar() or 0

    courses_count = (
        await db.execute(
            select(func.count(StudentReferral.id))
            .where(StudentReferral.distributor_id == distributor_id)
        )
    ).scalar() or 0

    revenue = (
        await db.execute(
            select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
            .where(CourseEnrollment.distributor_id == distributor_id)
        )
    ).scalar() or 0.0

    return {
        "distributor_id": distributor_id,
        "region": dist.region,
        "referral_code": dist.referral_code,
        "user_name": user.full_name if user else None,
        "total_students_referred": students_count,
        "total_courses_purchased": courses_count,
        "total_revenue_generated": float(revenue),
    }


# ── Phase 3: Advanced Reports ────────────────────────────────────────

from app.modules.certificates.models import Certificate
from app.modules.simulator.models import SimulatorAccount, PerformanceMetric
from app.modules.feedback.models import Feedback
from app.modules.placement.models import PlacementResult


async def get_admin_reports(db: AsyncSession) -> dict:
    """Aggregate analytics for admin reports dashboard."""
    total_students = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_courses = (await db.execute(select(func.count(Course.id)))).scalar() or 0
    total_certs = (await db.execute(select(func.count(Certificate.id)))).scalar() or 0
    total_sim = (await db.execute(select(func.count(SimulatorAccount.id)))).scalar() or 0
    total_fb = (await db.execute(select(func.count(Feedback.id)))).scalar() or 0
    avg_rating = (await db.execute(select(func.coalesce(func.avg(Feedback.rating), 0.0)))).scalar() or 0.0
    eligible_count = (await db.execute(
        select(func.count(PlacementResult.id)).where(PlacementResult.eligible == True)
    )).scalar() or 0

    return {
        "total_students": total_students,
        "total_courses": total_courses,
        "total_certificates": total_certs,
        "total_simulator_accounts": total_sim,
        "total_feedback": total_fb,
        "avg_feedback_rating": round(float(avg_rating), 2),
        "total_placements_eligible": eligible_count,
    }


async def get_admin_certificates(db: AsyncSession) -> dict:
    """Fetch certificate stats and list for admin."""
    total = (await db.execute(select(func.count(Certificate.id)))).scalar() or 0
    result = await db.execute(
        select(Certificate).order_by(Certificate.issued_at.desc()).limit(50)
    )
    certs = list(result.scalars().all())
    return {"total": total, "certificates": certs}


async def get_admin_simulator(db: AsyncSession) -> dict:
    """Fetch simulator usage stats and top performers."""
    total_accounts = (await db.execute(select(func.count(SimulatorAccount.id)))).scalar() or 0

    result = await db.execute(
        select(
            SimulatorAccount.user_id,
            SimulatorAccount.balance,
            PerformanceMetric.total_pnl,
            PerformanceMetric.win_rate,
            PerformanceMetric.total_trades,
        )
        .join(PerformanceMetric, PerformanceMetric.account_id == SimulatorAccount.id)
        .order_by(PerformanceMetric.total_pnl.desc())
        .limit(10)
    )
    rows = result.all()
    top_performers = [
        {
            "user_id": r[0],
            "balance": r[1],
            "total_pnl": r[2] or 0,
            "win_rate": r[3] or 0,
            "total_trades": r[4] or 0,
        }
        for r in rows
    ]
    return {"total_accounts": total_accounts, "top_performers": top_performers}

