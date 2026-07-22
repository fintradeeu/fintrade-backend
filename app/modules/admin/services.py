"""Admin module — service layer."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.modules.auth.models import User, Role
from app.modules.auth.services import get_or_create_role
from app.modules.courses.models import Course, CourseEnrollment
from app.modules.exams.models import EntranceExam
from app.modules.lectures.models import Lecture
from app.modules.distributors.models import Distributor, StudentReferral
from app.modules.offers.models import Offer, OfferRedemption
from app.modules.payments.models import PaymentTransaction
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
        .options(selectinload(User.roles), selectinload(User.distributor_profile))
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())
    total = (await db.execute(select(func.count(User.id)))).scalar() or 0
    return {"users": users, "total": total}


async def list_non_purchased_users(db: AsyncSession, skip: int = 0, limit: int = 50) -> dict:
    """List registered regular users who have not purchased any course."""
    
    # Subquery for user_ids who have enrolled in any course
    enrolled_user_ids = select(CourseEnrollment.user_id)
    privileged_roles = ("admin", "faculty", "super_admin", "distributor", "franchise_ib")
    
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles),
            selectinload(User.distributor_profile),
            selectinload(User.enrollments).selectinload(CourseEnrollment.course),
            selectinload(User.sessions)
        )
        .where(not_(User.id.in_(enrolled_user_ids)))
        .where(not_(User.roles.any(Role.name.in_(privileged_roles))))
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())

    if users:
        user_ids = [user.id for user in users]
        transactions_result = await db.execute(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.user_id.in_(user_ids),
                func.lower(PaymentTransaction.status) == "success",
            )
            .order_by(PaymentTransaction.updated_at.desc())
        )
        latest_transactions = {}
        for transaction in transactions_result.scalars().all():
            key = (transaction.user_id, transaction.course_id)
            if key not in latest_transactions:
                latest_transactions[key] = transaction

        redemptions_result = await db.execute(
            select(OfferRedemption)
            .options(selectinload(OfferRedemption.offer))
            .where(OfferRedemption.user_id.in_(user_ids))
            .order_by(OfferRedemption.redeemed_at.desc())
        )
        redemptions_by_user = {}
        for redemption in redemptions_result.scalars().all():
            redemptions_by_user.setdefault(redemption.user_id, []).append(redemption)

        for user in users:
            for enrollment in user.enrollments or []:
                transaction = latest_transactions.get((user.id, enrollment.course_id))
                if transaction:
                    setattr(enrollment, "coupon_code", transaction.coupon_code)
                    setattr(enrollment, "payment_txnid", transaction.txnid)
                    setattr(enrollment, "payment_mode", transaction.payment_mode)

                matching_redemption = None
                for redemption in redemptions_by_user.get(user.id, []):
                    offer = redemption.offer
                    if offer and offer.course_id and offer.course_id != enrollment.course_id:
                        continue
                    price_paid = enrollment.price_paid or 0.0
                    original_price = enrollment.course.price if enrollment.course else 0.0
                    same_paid_price = abs((redemption.discounted_price or 0.0) - price_paid) <= 0.01
                    same_original_price = abs((redemption.original_price or 0.0) - original_price) <= 0.01
                    if same_paid_price and same_original_price:
                        matching_redemption = redemption
                        break

                if matching_redemption and matching_redemption.offer:
                    setattr(enrollment, "coupon_code", matching_redemption.offer.code)
                    setattr(enrollment, "coupon_title", matching_redemption.offer.title)
    
    total = (await db.execute(
        select(func.count(User.id))
        .where(not_(User.id.in_(enrolled_user_ids)))
        .where(not_(User.roles.any(Role.name.in_(privileged_roles))))
    )).scalar() or 0
    
    return {"users": users, "total": total}


async def list_purchased_students(db: AsyncSession, skip: int = 0, limit: int = 50) -> dict:
    """List users who have purchased at least one course."""
    enrolled_user_ids = select(CourseEnrollment.user_id)
    
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles),
            selectinload(User.distributor_profile),
            selectinload(User.enrollments).selectinload(CourseEnrollment.course),
            selectinload(User.sessions)
        )
        .where(User.id.in_(enrolled_user_ids))
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())

    if users:
        user_ids = [user.id for user in users]
        from app.modules.kyc.models import KYCSubmission
        kyc_res = await db.execute(select(KYCSubmission).where(KYCSubmission.user_id.in_(user_ids)))
        kyc_map = {k.user_id: k.status for k in kyc_res.scalars().all()}
        for u in users:
            setattr(u, "kyc_status", kyc_map.get(u.id, "not_started"))

        transactions_result = await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id.in_(user_ids))
            .order_by(PaymentTransaction.updated_at.desc())
        )
        latest_transactions = {}
        offer_codes = set()
        for transaction in transactions_result.scalars().all():
            key = (transaction.user_id, transaction.course_id)
            if key not in latest_transactions or transaction.coupon_code:
                latest_transactions[key] = transaction
            if transaction.coupon_code:
                offer_codes.update(code.strip() for code in transaction.coupon_code.split(":") if code.strip())

        offers_by_code = {}
        if offer_codes:
            offers_result = await db.execute(select(Offer).where(Offer.code.in_(offer_codes)))
            offers_by_code = {offer.code: offer for offer in offers_result.scalars().all()}

        redemptions_result = await db.execute(
            select(OfferRedemption)
            .options(selectinload(OfferRedemption.offer))
            .where(OfferRedemption.user_id.in_(user_ids))
            .order_by(OfferRedemption.redeemed_at.desc())
        )
        redemptions_by_user = {}
        for redemption in redemptions_result.scalars().all():
            redemptions_by_user.setdefault(redemption.user_id, []).append(redemption)

        for user in users:
            for enrollment in user.enrollments or []:
                transaction = latest_transactions.get((user.id, enrollment.course_id))
                if transaction:
                    setattr(enrollment, "payment_txnid", transaction.txnid)
                    setattr(enrollment, "payment_mode", transaction.payment_mode)
                    if transaction.coupon_code:
                        setattr(enrollment, "coupon_code", transaction.coupon_code)
                        first_code = next((code.strip() for code in transaction.coupon_code.split(":") if code.strip()), None)
                        if first_code and first_code in offers_by_code:
                            setattr(enrollment, "coupon_title", offers_by_code[first_code].title)

                if getattr(enrollment, "coupon_code", None):
                    continue

                matching_redemption = None
                for redemption in redemptions_by_user.get(user.id, []):
                    offer = redemption.offer
                    if offer and offer.course_id and offer.course_id != enrollment.course_id:
                        continue
                    price_paid = enrollment.price_paid or 0.0
                    original_price = enrollment.course.price if enrollment.course else 0.0
                    same_paid_price = abs((redemption.discounted_price or 0.0) - price_paid) <= 0.01
                    same_original_price = abs((redemption.original_price or 0.0) - original_price) <= 0.01
                    if same_paid_price and same_original_price:
                        matching_redemption = redemption
                        break

                if matching_redemption and matching_redemption.offer:
                    setattr(enrollment, "coupon_code", matching_redemption.offer.code)
                    setattr(enrollment, "coupon_title", matching_redemption.offer.title)
    
    total = (await db.execute(
        select(func.count(User.id))
        .where(User.id.in_(enrolled_user_ids))
    )).scalar() or 0
    
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
    city: Optional[str] = None,
    permissions: Optional[dict] = None,
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
        city=city,
        hashed_password=hash_password(password),
        is_verified=True,  # Admin-created accounts are pre-verified
        created_by=created_by,
        permissions=permissions,
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    # Eager load the roles and distributor profile to prevent MissingGreenlet error in Pydantic schema validation
    result = await db.execute(select(User).options(selectinload(User.roles), selectinload(User.distributor_profile)).where(User.id == user.id))
    user = result.scalar_one()
    
    logger.info("admin_created_user", user_id=user.id, role=role_name, created_by=created_by)
    return user


async def create_distributor_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: str,
    region: str,
    referral_code: Optional[str],
    discount_percentage: float,
    created_by: int,
    phone: Optional[str] = None,
    city: Optional[str] = None,
    bank_account_holder_name: Optional[str] = None,
    bank_name: Optional[str] = None,
    bank_account_number: Optional[str] = None,
    bank_ifsc_code: Optional[str] = None,
    bank_upi_id: Optional[str] = None,
) -> tuple:
    """Admin creates a distributor: user + distributor profile."""
    if not referral_code:
        import string
        import random
        while True:
            code_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            generated_code = f"IB-{code_suffix}"
            existing_code = await db.execute(
                select(Distributor).where(Distributor.referral_code == generated_code)
            )
            if not existing_code.scalar_one_or_none():
                referral_code = generated_code
                break
    else:
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
        db, email, full_name, password, "distributor", created_by, phone, city
    )

    distributor = Distributor(
        user_id=user.id,
        region=region,
        referral_code=referral_code,
        discount_percentage=discount_percentage,
        bank_account_holder_name=bank_account_holder_name,
        bank_name=bank_name,
        bank_account_number=bank_account_number,
        bank_ifsc_code=bank_ifsc_code,
        bank_upi_id=bank_upi_id,
        verification_status="approved",
    )
    db.add(distributor)
    await db.flush()
    await db.refresh(distributor)
    logger.info("distributor_created", distributor_id=distributor.id, referral_code=referral_code)
    return user, distributor


async def update_user(db: AsyncSession, user_id: int, data: dict) -> User:
    """Update a user's details and their distributor profile if applicable."""
    # 1. Fetch user
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    # Check email uniqueness if changed
    new_email = data.get("email")
    if new_email and new_email != user.email:
        existing = await db.execute(select(User).where(User.email == new_email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
            
    # Update user fields
    phone_updated = False
    for field in ["email", "full_name", "phone", "city", "is_active", "permissions"]:
        if field in data and data[field] is not None:
            if field == "phone" and getattr(user, "phone") != data[field]:
                phone_updated = True
            setattr(user, field, data[field])
            
    if phone_updated:
        from app.modules.kyc.models import KYCSubmission
        kyc_result = await db.execute(
            select(KYCSubmission).where(KYCSubmission.user_id == user_id)
        )
        kyc = kyc_result.scalar_one_or_none()
        if kyc:
            kyc.mobile = user.phone
            
    # Check if user has a distributor profile and update distributor fields
    dist_result = await db.execute(
        select(Distributor).where(Distributor.user_id == user.id)
    )
    distributor = dist_result.scalar_one_or_none()
    
    if distributor:
            # Check referral code uniqueness if changed
            new_ref_code = data.get("referral_code")
            if new_ref_code and new_ref_code != distributor.referral_code:
                existing_code = await db.execute(
                    select(Distributor).where(Distributor.referral_code == new_ref_code)
                )
                if existing_code.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Referral code already exists",
                    )
            
            for field in [
                "region",
                "referral_code",
                "discount_percentage",
                "bank_account_holder_name",
                "bank_name",
                "bank_account_number",
                "bank_ifsc_code",
                "bank_upi_id",
                "verification_status",
            ]:
                if field in data and data[field] is not None:
                    setattr(distributor, field, data[field])
                    
    await db.flush()
    # Re-fetch with roles and distributor profile loaded
    result = await db.execute(
        select(User).options(selectinload(User.roles), selectinload(User.distributor_profile)).where(User.id == user_id)
    )
    user = result.scalar_one()
    
    logger.info("admin_updated_user", user_id=user.id)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    """Delete a user account."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.distributor_profile))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.distributor_profile is not None:
        await db.delete(user.distributor_profile)
        await db.flush()
    await db.delete(user)
    await db.flush()
    logger.info("admin_deleted_user", user_id=user_id)


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
            select(func.count(CourseEnrollment.id))
            .where(
                CourseEnrollment.distributor_id == distributor_id,
                CourseEnrollment.is_active == True,  # noqa: E712
            )
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

    from datetime import datetime, timezone
    from app.modules.exams.models import CourseExamResult
    
    now = datetime.now(timezone.utc)
    revenue_trend = []
    exam_pass_rate = []
    
    for i in range(5, -1, -1):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
            
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        month_end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
        
        # Monthly Revenue
        monthly_rev = (await db.execute(
            select(func.coalesce(func.sum(PaymentTransaction.amount), 0.0))
            .where(
                PaymentTransaction.status == "success",
                PaymentTransaction.updated_at >= month_start,
                PaymentTransaction.updated_at < month_end
            )
        )).scalar() or 0.0
        
        revenue_trend.append({
            "month": month_start.strftime("%b"),
            "revenue": float(monthly_rev)
        })
        
        # Exam pass rate
        total_exams = (await db.execute(
            select(func.count(CourseExamResult.id))
            .where(
                CourseExamResult.evaluated_at >= month_start,
                CourseExamResult.evaluated_at < month_end
            )
        )).scalar() or 0
        
        passed_exams = (await db.execute(
            select(func.count(CourseExamResult.id))
            .where(
                CourseExamResult.passed == True,
                CourseExamResult.evaluated_at >= month_start,
                CourseExamResult.evaluated_at < month_end
            )
        )).scalar() or 0
        
        pass_rate = (passed_exams / total_exams * 100) if total_exams > 0 else 0
        
        exam_pass_rate.append({
            "month": month_start.strftime("%b"),
            "passRate": round(pass_rate, 2)
        })

    return {
        "total_students": total_students,
        "total_courses": total_courses,
        "total_certificates": total_certs,
        "total_simulator_accounts": total_sim,
        "total_feedback": total_fb,
        "avg_feedback_rating": round(float(avg_rating), 2),
        "total_placements_eligible": eligible_count,
        "revenue_trend": revenue_trend,
        "exam_pass_rate": exam_pass_rate,
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

