"""Services for IB commission and wallet management."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.commissions.models import (
    CommissionAuditLog,
    CourseIBCommission,
    IBWallet,
    WalletTransaction,
    WithdrawalRequest,
)
from app.modules.courses.models import Course, CourseEnrollment
from app.modules.distributors.models import Distributor


async def audit(db: AsyncSession, user_id: Optional[int], action: str, description: str, ip_address: Optional[str] = None) -> None:
    db.add(CommissionAuditLog(user_id=user_id, action=action, description=description, ip_address=ip_address))


async def get_or_create_wallet(db: AsyncSession, ib_id: int) -> IBWallet:
    result = await db.execute(select(IBWallet).where(IBWallet.ib_id == ib_id))
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet
    wallet = IBWallet(ib_id=ib_id)
    db.add(wallet)
    await db.flush()
    return wallet


async def list_commission_courses(db: AsyncSession) -> list[dict]:
    courses_res = await db.execute(select(Course).order_by(Course.created_at.desc()))
    courses = courses_res.scalars().all()
    total_ibs = (await db.execute(select(func.count(Distributor.id)))).scalar() or 0
    configured_res = await db.execute(
        select(CourseIBCommission.course_id, func.count(CourseIBCommission.id)).group_by(CourseIBCommission.course_id)
    )
    configured = {row[0]: row[1] for row in configured_res.all()}
    return [
        {
            "course_id": c.id,
            "course_title": c.title,
            "course_price": float(c.price or 0),
            "total_ibs": total_ibs,
            "configured_ibs": configured.get(c.id, 0),
        }
        for c in courses
    ]


async def list_ib_commissions_for_course(db: AsyncSession, course_id: int) -> list[dict]:
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    result = await db.execute(
        select(Distributor)
        .options(selectinload(Distributor.user))
        .order_by(Distributor.created_at.desc())
    )
    ibs = result.scalars().all()

    commissions_res = await db.execute(
        select(CourseIBCommission).where(CourseIBCommission.course_id == course_id)
    )
    commission_map = {c.ib_id: c for c in commissions_res.scalars().all()}

    rows = []
    for ib in ibs:
        cfg = commission_map.get(ib.id)
        rows.append(
            {
                "ib_id": ib.id,
                "user_id": ib.user_id,
                "ib_name": ib.user.full_name if ib.user else None,
                "email": ib.user.email if ib.user else None,
                "mobile": ib.user.phone if ib.user else None,
                "commission_id": cfg.id if cfg else None,
                "commission_type": cfg.commission_type if cfg else None,
                "commission_value": cfg.commission_value if cfg else None,
                "is_active": bool(cfg.is_active) if cfg else False,
            }
        )
    return rows


async def upsert_course_ib_commission(
    db: AsyncSession,
    course_id: int,
    ib_id: int,
    commission_type: str,
    commission_value: float,
    is_active: bool,
    user_id: Optional[int] = None,
) -> CourseIBCommission:
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    ib = await db.get(Distributor, ib_id)
    if not ib:
        raise HTTPException(status_code=404, detail="IB not found")

    course_price = float(course.price or 0)
    if commission_type == "percentage" and commission_value > 100:
        raise HTTPException(status_code=400, detail="Percentage commission cannot exceed 100")
    if commission_type == "flat" and commission_value >= course_price:
        raise HTTPException(status_code=400, detail="Flat commission must be less than course price")

    result = await db.execute(
        select(CourseIBCommission).where(
            CourseIBCommission.course_id == course_id,
            CourseIBCommission.ib_id == ib_id,
        )
    )
    commission = result.scalar_one_or_none()
    action = "Commission Updated" if commission else "Commission Created"
    if not commission:
        commission = CourseIBCommission(course_id=course_id, ib_id=ib_id)
        db.add(commission)

    commission.commission_type = commission_type
    commission.commission_value = round(float(commission_value), 2)
    commission.is_active = is_active
    commission.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await audit(db, user_id, action, f"{action} for course {course_id}, IB {ib_id}")
    return commission


async def set_commission_status(db: AsyncSession, commission_id: int, is_active: bool, user_id: Optional[int] = None) -> CourseIBCommission:
    commission = await db.get(CourseIBCommission, commission_id)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission setup not found")
    commission.is_active = is_active
    commission.updated_at = datetime.now(timezone.utc)
    await audit(db, user_id, "Commission Status Changed", f"Commission {commission_id} active={is_active}")
    await db.flush()
    return commission


async def credit_commission_for_enrollment(db: AsyncSession, enrollment: CourseEnrollment) -> None:
    if not enrollment.distributor_id:
        return

    reference_no = f"ENROLL-{enrollment.id}"
    existing = await db.execute(select(WalletTransaction).where(WalletTransaction.reference_no == reference_no))
    if existing.scalar_one_or_none():
        return

    result = await db.execute(
        select(CourseIBCommission).where(
            CourseIBCommission.course_id == enrollment.course_id,
            CourseIBCommission.ib_id == enrollment.distributor_id,
            CourseIBCommission.is_active == True,
        )
    )
    commission = result.scalar_one_or_none()
    if not commission:
        return

    course = await db.get(Course, enrollment.course_id)
    base_amount = float(course.price or enrollment.price_paid or 0)
    if commission.commission_type == "flat":
        amount = float(commission.commission_value)
    else:
        amount = base_amount * float(commission.commission_value) / 100
    amount = round(max(amount, 0.0), 2)
    if amount <= 0:
        return

    wallet = await get_or_create_wallet(db, enrollment.distributor_id)
    wallet.available_balance = round(wallet.available_balance + amount, 2)
    wallet.total_earned = round(wallet.total_earned + amount, 2)
    tx = WalletTransaction(
        ib_id=enrollment.distributor_id,
        student_id=enrollment.user_id,
        course_id=enrollment.course_id,
        commission_amount=amount,
        transaction_type="credit",
        description=f"Commission credited for {course.title if course else 'course purchase'}",
        reference_no=reference_no,
        status="paid",
        balance_after=wallet.available_balance,
    )
    db.add(tx)
    await audit(db, None, "Wallet Credited", f"Credited ₹{amount} to IB {enrollment.distributor_id} for enrollment {enrollment.id}")
    await db.flush()


async def wallet_summary(db: AsyncSession, ib_id: int) -> dict:
    wallet = await get_or_create_wallet(db, ib_id)
    pending = (
        await db.execute(
            select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)).where(
                WithdrawalRequest.ib_id == ib_id,
                WithdrawalRequest.status.in_(["pending", "approved"]),
            )
        )
    ).scalar() or 0.0
    return {
        "ib_id": ib_id,
        "available_balance": float(wallet.available_balance),
        "total_earned": float(wallet.total_earned),
        "total_withdrawn": float(wallet.total_withdrawn),
        "pending_withdrawals": float(pending),
    }


async def list_wallet_transactions(db: AsyncSession, ib_id: Optional[int] = None) -> list[WalletTransaction]:
    stmt = (
        select(WalletTransaction)
        .options(selectinload(WalletTransaction.student), selectinload(WalletTransaction.course))
        .order_by(WalletTransaction.created_at.desc())
    )
    if ib_id:
        stmt = stmt.where(WalletTransaction.ib_id == ib_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_withdrawal(db: AsyncSession, ib_id: int, data: dict) -> WithdrawalRequest:
    amount = round(float(data["amount"]), 2)
    wallet = await get_or_create_wallet(db, ib_id)
    if amount < 500:
        raise HTTPException(status_code=400, detail="Minimum withdrawal amount is ₹500")
    if amount > wallet.available_balance:
        raise HTTPException(status_code=400, detail="Withdrawal amount cannot exceed available balance")

    wallet.available_balance = round(wallet.available_balance - amount, 2)
    tx = WalletTransaction(
        ib_id=ib_id,
        commission_amount=amount,
        transaction_type="debit",
        description="Withdrawal request",
        reference_no=f"WDR-{uuid4().hex[:12].upper()}",
        status="pending",
        balance_after=wallet.available_balance,
    )
    db.add(tx)
    await db.flush()
    req = WithdrawalRequest(
        ib_id=ib_id,
        amount=amount,
        withdrawal_method=data["withdrawal_method"],
        account_holder_name=data.get("account_holder_name"),
        bank_name=data.get("bank_name"),
        account_number=data.get("account_number"),
        ifsc_code=data.get("ifsc_code"),
        upi_id=data.get("upi_id"),
        qr_code_image=data.get("qr_code_image"),
        wallet_transaction_id=tx.id,
    )
    db.add(req)
    await audit(db, None, "Withdrawal Requested", f"IB {ib_id} requested ₹{amount}")
    await db.flush()
    return req


async def list_withdrawals(db: AsyncSession, ib_id: Optional[int] = None) -> list[WithdrawalRequest]:
    stmt = select(WithdrawalRequest).options(selectinload(WithdrawalRequest.ib).selectinload(Distributor.user)).order_by(WithdrawalRequest.requested_at.desc())
    if ib_id:
        stmt = stmt.where(WithdrawalRequest.ib_id == ib_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def approve_withdrawal(db: AsyncSession, withdrawal_id: int, admin_id: int, remarks: Optional[str] = None) -> WithdrawalRequest:
    req = await db.get(WithdrawalRequest, withdrawal_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")
    req.status = "approved"
    req.approved_at = datetime.now(timezone.utc)
    req.admin_remarks = remarks
    if req.wallet_transaction_id:
        tx = await db.get(WalletTransaction, req.wallet_transaction_id)
        if tx:
            tx.status = "approved"
    await audit(db, admin_id, "Withdrawal Approved", f"Withdrawal {withdrawal_id} approved")
    await db.flush()
    return req


async def reject_withdrawal(db: AsyncSession, withdrawal_id: int, admin_id: int, remarks: Optional[str] = None) -> WithdrawalRequest:
    req = await db.get(WithdrawalRequest, withdrawal_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail="Only pending or approved requests can be rejected")
    wallet = await get_or_create_wallet(db, req.ib_id)
    wallet.available_balance = round(wallet.available_balance + req.amount, 2)
    req.status = "rejected"
    req.admin_remarks = remarks
    if req.wallet_transaction_id:
        tx = await db.get(WalletTransaction, req.wallet_transaction_id)
        if tx:
            tx.status = "rejected"
            tx.balance_after = wallet.available_balance
    await audit(db, admin_id, "Withdrawal Rejected", f"Withdrawal {withdrawal_id} rejected")
    await db.flush()
    return req


async def mark_withdrawal_paid(db: AsyncSession, withdrawal_id: int, admin_id: int, proof_file: Optional[str], utr_number: Optional[str], transaction_reference: Optional[str]) -> WithdrawalRequest:
    from app.modules.commissions.models import PaymentProof

    req = await db.get(WithdrawalRequest, withdrawal_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if req.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail="Only pending or approved requests can be marked paid")

    wallet = await get_or_create_wallet(db, req.ib_id)
    wallet.total_withdrawn = round(wallet.total_withdrawn + req.amount, 2)
    req.status = "paid"
    req.paid_at = datetime.now(timezone.utc)
    req.payment_proof = proof_file
    if req.wallet_transaction_id:
        tx = await db.get(WalletTransaction, req.wallet_transaction_id)
        if tx:
            tx.status = "paid"
    db.add(PaymentProof(withdrawal_request_id=req.id, utr_number=utr_number, transaction_reference=transaction_reference, proof_file=proof_file, uploaded_by=admin_id))
    await audit(db, admin_id, "Withdrawal Paid", f"Withdrawal {withdrawal_id} paid")
    await db.flush()
    return req


async def commission_report(db: AsyncSession) -> dict:
    total_sales = (await db.execute(select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0)).where(CourseEnrollment.distributor_id.isnot(None)))).scalar() or 0.0
    total_commission = (await db.execute(select(func.coalesce(func.sum(WalletTransaction.commission_amount), 0.0)).where(WalletTransaction.transaction_type == "credit"))).scalar() or 0.0
    total_paid = (await db.execute(select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)).where(WithdrawalRequest.status == "paid"))).scalar() or 0.0
    pending_commission = (await db.execute(select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)).where(WithdrawalRequest.status.in_(["pending", "approved"])))).scalar() or 0.0
    return {"total_sales": float(total_sales), "total_commission": float(total_commission), "total_paid": float(total_paid), "pending_commission": float(pending_commission)}


async def withdrawal_report(db: AsyncSession) -> dict:
    requested = (await db.execute(select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)))).scalar() or 0.0
    paid = (await db.execute(select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)).where(WithdrawalRequest.status == "paid"))).scalar() or 0.0
    pending = (await db.execute(select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0)).where(WithdrawalRequest.status.in_(["pending", "approved"])))).scalar() or 0.0
    return {"requested_amount": float(requested), "paid_amount": float(paid), "pending_amount": float(pending)}


async def ib_wise_revenue_report(db: AsyncSession) -> dict:
    """Per-Franchise-IB revenue breakdown: gross sales, IB commission, superadmin net."""

    # Fetch all distributors (Franchise IBs) with their user info
    result = await db.execute(
        select(Distributor)
        .options(selectinload(Distributor.user))
        .order_by(Distributor.created_at.desc())
    )
    ibs = result.scalars().all()

    rows = []
    total_gross = 0.0
    total_commission_paid = 0.0
    total_net = 0.0

    for ib in ibs:
        # Gross revenue collected from students enrolled via this IB
        gross_res = await db.execute(
            select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
            .where(CourseEnrollment.distributor_id == ib.id)
        )
        gross = float(gross_res.scalar() or 0.0)

        # Student count enrolled via this IB
        student_count_res = await db.execute(
            select(func.count(CourseEnrollment.id))
            .where(CourseEnrollment.distributor_id == ib.id)
        )
        student_count = int(student_count_res.scalar() or 0)

        # Total commission earned by this IB (credited to wallet)
        commission_res = await db.execute(
            select(func.coalesce(func.sum(WalletTransaction.commission_amount), 0.0))
            .where(
                WalletTransaction.ib_id == ib.id,
                WalletTransaction.transaction_type == "credit",
            )
        )
        commission_earned = float(commission_res.scalar() or 0.0)

        # Total commission already paid out (withdrawn and marked paid)
        paid_res = await db.execute(
            select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0))
            .where(WithdrawalRequest.ib_id == ib.id, WithdrawalRequest.status == "paid")
        )
        commission_paid_out = float(paid_res.scalar() or 0.0)

        # Pending commissions (approved/pending withdrawal)
        pending_res = await db.execute(
            select(func.coalesce(func.sum(WithdrawalRequest.amount), 0.0))
            .where(WithdrawalRequest.ib_id == ib.id, WithdrawalRequest.status.in_(["pending", "approved"]))
        )
        pending_withdrawal = float(pending_res.scalar() or 0.0)

        # Wallet current balance
        wallet_res = await db.execute(select(IBWallet).where(IBWallet.ib_id == ib.id))
        wallet = wallet_res.scalar_one_or_none()
        wallet_balance = float(wallet.available_balance) if wallet else 0.0

        # Superadmin net = gross revenue - total commission earned by IB
        net_revenue = round(gross - commission_earned, 2)

        total_gross += gross
        total_commission_paid += commission_earned
        total_net += net_revenue

        rows.append({
            "ib_id": ib.id,
            "ib_name": ib.user.full_name if ib.user else f"IB #{ib.id}",
            "ib_email": ib.user.email if ib.user else None,
            "referral_code": ib.referral_code,
            "student_count": student_count,
            "gross_revenue": round(gross, 2),
            "commission_earned": round(commission_earned, 2),
            "commission_paid_out": round(commission_paid_out, 2),
            "pending_withdrawal": round(pending_withdrawal, 2),
            "wallet_balance": round(wallet_balance, 2),
            "superadmin_net_revenue": net_revenue,
        })

    # Also compute direct (no IB) revenue
    direct_gross_res = await db.execute(
        select(func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
        .where(CourseEnrollment.distributor_id.is_(None))
    )
    direct_gross = float(direct_gross_res.scalar() or 0.0)

    direct_student_count_res = await db.execute(
        select(func.count(CourseEnrollment.id))
        .where(CourseEnrollment.distributor_id.is_(None))
    )
    direct_student_count = int(direct_student_count_res.scalar() or 0)

    return {
        "summary": {
            "total_gross_revenue": round(total_gross + direct_gross, 2),
            "total_ib_commission": round(total_commission_paid, 2),
            "total_superadmin_net": round(total_net + direct_gross, 2),
            "direct_revenue": round(direct_gross, 2),
            "direct_student_count": direct_student_count,
            "total_ib_count": len(rows),
        },
        "ib_rows": rows,
    }
