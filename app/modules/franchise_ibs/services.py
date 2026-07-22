"""Franchise IBs module — Business logic and database operations."""

import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional, List

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
        commission_percentage=data.commission_percentage if data.commission_percentage is not None else 100.0,
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
    raw_revenue = float(row[1]) if row and row[1] else 0.0

    fib_stmt = select(FranchiseIB.referral_code, FranchiseIB.commission_percentage).where(FranchiseIB.id == franchise_id)
    fib_res = await db.execute(fib_stmt)
    fib_data = fib_res.first()
    referral_code = fib_data[0] if fib_data else None
    commission_pct = fib_data[1] if fib_data and fib_data[1] is not None else 100.0

    total_revenue = raw_revenue * (commission_pct / 100.0)

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

    # Chart data is below

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


from app.modules.franchise_ibs.models import FranchiseIBWallet, FranchiseIBWithdrawalRequest
from app.modules.courses.models import CourseEnrollment
from fastapi import HTTPException


async def get_or_create_franchise_wallet(db: AsyncSession, franchise_ib_id: int) -> FranchiseIBWallet:
    stmt = select(FranchiseIBWallet).where(FranchiseIBWallet.franchise_ib_id == franchise_ib_id)
    res = await db.execute(stmt)
    wallet = res.scalar_one_or_none()
    if not wallet:
        wallet = FranchiseIBWallet(franchise_ib_id=franchise_ib_id)
        db.add(wallet)
        await db.flush()
    return wallet


async def get_franchise_wallet_summary(db: AsyncSession, franchise_ib_id: int) -> dict:
    wallet = await get_or_create_franchise_wallet(db, franchise_ib_id)
    fib = await db.get(FranchiseIB, franchise_ib_id)
    commission_pct = fib.commission_percentage if fib and fib.commission_percentage is not None else 100.0

    # Calculate gross revenue from payments & course enrollments
    # 1. Payments from students linked to this Franchise IB via StudentReferral
    pmt_stmt = (
        select(func.coalesce(func.sum(PaymentTransaction.amount), 0.0))
        .select_from(PaymentTransaction)
        .join(StudentReferral, StudentReferral.student_id == PaymentTransaction.user_id)
        .where(StudentReferral.franchise_ib_id == franchise_ib_id)
        .where(PaymentTransaction.status.in_(["success", "pending_verification", "completed"]))
    )
    pmt_revenue = float((await db.execute(pmt_stmt)).scalar() or 0.0)

    # 2. Course enrollments via sub-IBs under this Franchise IB
    sub_ib_ids_stmt = select(Distributor.id).where(Distributor.franchise_id == franchise_ib_id)
    sub_ib_ids = (await db.execute(sub_ib_ids_stmt)).scalars().all()
    
    enr_revenue = 0.0
    if sub_ib_ids:
        enr_stmt = (
            select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
            .where(CourseEnrollment.distributor_id.in_(sub_ib_ids))
        )
        enr_revenue = float((await db.execute(enr_stmt)).scalar() or 0.0)

    gross_revenue = max(pmt_revenue, enr_revenue)
    total_earned = round(gross_revenue * (commission_pct / 100.0), 2)

    # Calculate total withdrawn (paid)
    withdrawn_stmt = select(func.coalesce(func.sum(FranchiseIBWithdrawalRequest.amount), 0.0)).where(
        FranchiseIBWithdrawalRequest.franchise_ib_id == franchise_ib_id,
        FranchiseIBWithdrawalRequest.status == "paid"
    )
    total_withdrawn = round(float((await db.execute(withdrawn_stmt)).scalar() or 0.0), 2)

    # Calculate pending withdrawals
    pending_stmt = select(func.coalesce(func.sum(FranchiseIBWithdrawalRequest.amount), 0.0)).where(
        FranchiseIBWithdrawalRequest.franchise_ib_id == franchise_ib_id,
        FranchiseIBWithdrawalRequest.status.in_(["pending", "approved"])
    )
    pending_withdrawals = round(float((await db.execute(pending_stmt)).scalar() or 0.0), 2)

    available_balance = max(0.0, round(total_earned - total_withdrawn - pending_withdrawals, 2))

    # Update wallet record
    wallet.total_earned = total_earned
    wallet.total_withdrawn = total_withdrawn
    wallet.available_balance = available_balance
    await db.flush()

    return {
        "available_balance": available_balance,
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
        "pending_withdrawals": pending_withdrawals,
    }


async def create_franchise_withdrawal(db: AsyncSession, franchise_ib_id: int, data: dict) -> FranchiseIBWithdrawalRequest:
    amount = float(data.get("amount", 0.0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    summary = await get_franchise_wallet_summary(db, franchise_ib_id)
    if amount > summary["available_balance"]:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available balance is ₹{summary['available_balance']}"
        )

    method = data.get("withdrawal_method", "bank")
    if method == "bank":
        if not data.get("account_number") or not data.get("ifsc_code"):
            raise HTTPException(status_code=400, detail="Bank Account Number and IFSC Code are required")
        if data.get("account_number") != data.get("confirm_account_number"):
            raise HTTPException(status_code=400, detail="Bank Account Numbers do not match")
    elif method == "upi":
        if not data.get("upi_id") and not data.get("qr_code_image"):
            raise HTTPException(status_code=400, detail="UPI ID or QR Code image is required")

    req = FranchiseIBWithdrawalRequest(
        franchise_ib_id=franchise_ib_id,
        amount=amount,
        withdrawal_method=method,
        account_holder_name=data.get("account_holder_name"),
        bank_name=data.get("bank_name"),
        account_number=data.get("account_number"),
        ifsc_code=data.get("ifsc_code"),
        upi_id=data.get("upi_id"),
        qr_code_image=data.get("qr_code_image"),
        status="pending",
    )
    db.add(req)
    await db.flush()

    # Re-sync wallet
    await get_franchise_wallet_summary(db, franchise_ib_id)
    return req


async def list_franchise_withdrawals(db: AsyncSession, franchise_ib_id: Optional[int] = None) -> list[FranchiseIBWithdrawalRequest]:
    stmt = select(FranchiseIBWithdrawalRequest).options(
        selectinload(FranchiseIBWithdrawalRequest.franchise_ib).selectinload(FranchiseIB.user)
    ).order_by(desc(FranchiseIBWithdrawalRequest.requested_at))
    if franchise_ib_id is not None:
        stmt = stmt.where(FranchiseIBWithdrawalRequest.franchise_ib_id == franchise_ib_id)
    res = await db.execute(stmt)
    return res.scalars().all()


async def approve_franchise_withdrawal(db: AsyncSession, request_id: int, remarks: Optional[str] = None) -> FranchiseIBWithdrawalRequest:
    req = await db.get(FranchiseIBWithdrawalRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")
    req.status = "approved"
    req.approved_at = datetime.now(timezone.utc)
    req.admin_remarks = remarks
    await db.flush()
    return req


async def reject_franchise_withdrawal(db: AsyncSession, request_id: int, remarks: Optional[str] = None) -> FranchiseIBWithdrawalRequest:
    req = await db.get(FranchiseIBWithdrawalRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail="Only pending or approved requests can be rejected")
    req.status = "rejected"
    req.admin_remarks = remarks
    await db.flush()
    await get_franchise_wallet_summary(db, req.franchise_ib_id)
    return req


async def mark_paid_franchise_withdrawal(
    db: AsyncSession,
    request_id: int,
    proof_file: Optional[str],
    utr_number: Optional[str],
    transaction_reference: Optional[str]
) -> FranchiseIBWithdrawalRequest:
    req = await db.get(FranchiseIBWithdrawalRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail="Only pending or approved requests can be marked paid")
    req.status = "paid"
    req.paid_at = datetime.now(timezone.utc)
    req.payment_proof = proof_file
    req.utr_number = utr_number
    req.transaction_reference = transaction_reference
    await db.flush()
    await get_franchise_wallet_summary(db, req.franchise_ib_id)
    return req
