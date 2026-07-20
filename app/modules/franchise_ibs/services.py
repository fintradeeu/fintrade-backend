"""Franchise IBs module — Business logic and database operations."""

import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timezone

from app.modules.franchise_ibs.models import FranchiseIB
from app.modules.auth.models import User, Role
from app.core.security import hash_password
from app.modules.franchise_ibs import schemas
from app.modules.distributors.models import Distributor, StudentReferral
from app.modules.payments.models import PaymentTransaction


def generate_referral_code() -> str:
    """Generate a unique referral code for a Franchise IB."""
    random_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"FIB{random_str}"


async def create_franchise_ib(db: AsyncSession, data: schemas.FranchiseIBCreate, created_by_admin: bool = False) -> FranchiseIB:
    # Check if user already exists
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ValueError("User with this email already exists")

    # Get franchise_ib role
    stmt = select(Role).where(Role.name == "franchise_ib")
    result = await db.execute(stmt)
    fib_role = result.scalar_one_or_none()
    if not fib_role:
        raise ValueError("Franchise IB role not found in system")

    # Create user
    user = User(
        email=data.email,
        full_name=data.full_name,
        phone=data.mobile_no,
        hashed_password=hash_password(data.password),
        is_active=True,
        is_verified=True,  # Auto-verify if admin creates, maybe?
    )
    user.roles.append(fib_role)
    db.add(user)
    await db.flush()

    # Generate unique referral code
    ref_code = generate_referral_code()
    
    # Ensure it's unique
    while True:
        check_stmt = select(FranchiseIB).where(FranchiseIB.referral_code == ref_code)
        check_res = await db.execute(check_stmt)
        if not check_res.scalar_one_or_none():
            break
        ref_code = generate_referral_code()

    # Create profile
    profile = FranchiseIB(
        user_id=user.id,
        referral_code=ref_code,
        pan_number=data.pan_number,
        aadhaar_number=data.aadhaar_number,
        bank_account_holder_name=data.bank_account_holder_name,
        bank_name=data.bank_name,
        bank_account_number=data.bank_account_number,
        bank_ifsc_code=data.bank_ifsc_code,
        self_registered="no" if created_by_admin else "yes",
        verification_status="approved" if created_by_admin else "pending",
    )
    db.add(profile)
    await db.flush()
    return profile


async def get_franchise_ib_by_user(db: AsyncSession, user_id: int) -> FranchiseIB:
    stmt = select(FranchiseIB).where(FranchiseIB.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


from sqlalchemy import select, func

async def get_dashboard_stats(db: AsyncSession, franchise_id: int) -> schemas.FranchiseIBDashboardStats:
    # 1. Total IBs
    stmt = select(func.count(Distributor.id)).where(Distributor.franchise_id == franchise_id)
    total_ibs = (await db.execute(stmt)).scalar() or 0
    
    # 2. Total Students
    stmt = select(func.count(StudentReferral.id)).where(StudentReferral.franchise_ib_id == franchise_id)
    total_students = (await db.execute(stmt)).scalar() or 0
    
    # 3. Revenue & Enrollments
    # Join PaymentTransaction with StudentReferral to get payments made by students under this Franchise IB
    stmt = (
        select(
            func.count(PaymentTransaction.id),
            func.sum(PaymentTransaction.amount)
        )
        .select_from(PaymentTransaction)
        .join(StudentReferral, StudentReferral.student_id == PaymentTransaction.user_id)
        .where(StudentReferral.franchise_ib_id == franchise_id)
        .where(PaymentTransaction.status.in_(["success", "pending_verification", "completed"]))
    )
    result = await db.execute(stmt)
    row = result.first()
    
    total_enrollments = row[0] if row and row[0] else 0
    total_revenue = float(row[1]) if row and row[1] else 0.0

    # Chart data (Mocked slightly for demonstration, can be expanded to group by date)
    revenue_chart_data = [
        {"name": "Jan", "value": 0}, {"name": "Feb", "value": 0},
        {"name": "Mar", "value": 0}, {"name": "Apr", "value": total_revenue * 0.2},
        {"name": "May", "value": total_revenue * 0.5}, {"name": "Jun", "value": total_revenue * 0.3},
        {"name": "Jul", "value": total_revenue},
    ]
    enrollment_chart_data = [
        {"name": "Jan", "value": 0}, {"name": "Feb", "value": 0},
        {"name": "Mar", "value": 0}, {"name": "Apr", "value": total_enrollments * 0.2},
        {"name": "May", "value": total_enrollments * 0.5}, {"name": "Jun", "value": total_enrollments * 0.3},
        {"name": "Jul", "value": total_enrollments},
    ]

    fib_stmt = select(FranchiseIB.referral_code).where(FranchiseIB.id == franchise_id)
    referral_code = (await db.execute(fib_stmt)).scalar()

    return schemas.FranchiseIBDashboardStats(
        referral_code=referral_code,
        total_students=total_students,
        active_students=total_students,
        total_ibs=total_ibs,
        today_registrations=0,
        monthly_registrations=0,
        pending_payments=0,
        total_enrollments=total_enrollments,
        total_revenue=total_revenue,
        razorpay_revenue=0.0,
        cash_revenue=0.0,
        cheque_revenue=0.0,
        revenue_chart_data=revenue_chart_data,
        enrollment_chart_data=enrollment_chart_data
    )
