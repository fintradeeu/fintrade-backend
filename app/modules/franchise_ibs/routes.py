"""Franchise IBs module — API Routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from datetime import datetime, timezone, timedelta

from app.db.database import get_db
from app.core.security import get_current_user
from app.modules.auth.models import User, Role
from app.modules.franchise_ibs import schemas
from app.modules.franchise_ibs.models import FranchiseIB
from app.modules.distributors.models import Distributor
from app.modules.auth.schemas import MessageResponse

from app.modules.franchise_ibs import schemas, services
from app.modules.distributors.schemas import ManualStudentRegisterRequest

router = APIRouter(prefix="/franchise-ibs", tags=["Franchise IBs"])


@router.post("/", response_model=schemas.FranchiseIBResponse)
async def register_franchise_ib(
    data: schemas.FranchiseIBCreate,
    db: AsyncSession = Depends(get_db),
    # Uncomment to require super_admin to create:
    # current_user: User = Depends(get_current_user) 
):
    """Register a new Franchise IB."""
    try:
        profile = await services.create_franchise_ib(db, data, created_by_admin=False)
        await db.commit()
        
        # Send email with credentials
        from app.utils.smtp_notifications import send_email
        import asyncio
        subject = "Welcome to FinTrade Edutech - Franchise IB Account Details"
        html_body = f"""
        <html>
          <body>
            <p>Dear {data.full_name},</p>
            <p>Your Franchise IB account has been successfully created.</p>
            <p><strong>Login Details:</strong></p>
            <ul>
              <li><strong>Username:</strong> {data.email}</li>
              <li><strong>Password:</strong> {data.password}</li>
            </ul>
            <p>You can now log in to the Franchise IB dashboard.</p>
            <p>Best regards,<br>FinTrade Edutech Team</p>
          </body>
        </html>
        """
        asyncio.create_task(send_email(data.email, subject, html_body))
        
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard", response_model=schemas.FranchiseIBDashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics for the logged-in Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    stats = await services.get_dashboard_stats(db, profile.id)
    return stats


@router.get("/ibs")
async def get_franchise_ibs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all IBs (Distributors) under the current Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    
    # Fetch IBs
    stmt = select(Distributor, User).join(User, User.id == Distributor.user_id).where(Distributor.franchise_id == profile.id)
    result = await db.execute(stmt)
    ibs = []
    for dist, user in result.all():
        ibs.append({
            "id": dist.id,
            "referral_code": dist.referral_code,
            "region": dist.region,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "created_at": dist.created_at
        })
    return {"status": "success", "data": ibs}


@router.get("/students")
async def get_franchise_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all students and their journey timeline under the current Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    
    from app.modules.distributors.services import list_referral_journeys
    journeys = await list_referral_journeys(db, franchise_ib_id=profile.id)
    
    return {"status": "success", "data": journeys}


@router.post("/manual-register", status_code=201)
async def manual_register_student(
    body: ManualStudentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually register a student and optionally record offline payment."""
    from app.modules.distributors.services import manual_register_student as _manual_register
    
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    return await _manual_register(db, data=body, franchise_ib_id=profile.id)


@router.put("/students/{student_id}", response_model=MessageResponse)
async def update_franchise_student(
    student_id: int,
    body: schemas.StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update details of a student registered under the Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    # Check if student is referred by this Franchise IB
    from app.modules.distributors.models import StudentReferral
    from app.modules.auth.models import User
    
    stmt = select(StudentReferral).where(
        StudentReferral.student_id == student_id,
        StudentReferral.franchise_ib_id == profile.id
    )
    res = await db.execute(stmt)
    referral = res.scalar_one_or_none()
    if not referral:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this student's details"
        )
        
    # Fetch the student user
    student = await db.get(User, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Update fields
    if body.full_name is not None:
        student.full_name = body.full_name
    if body.phone is not None:
        # Check if phone number is already taken by another user
        if body.phone != student.phone:
            dup = await db.execute(select(User).where(User.phone == body.phone))
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Phone number already registered by another user")
        student.phone = body.phone
    if body.city is not None:
        student.city = body.city
        
    await db.commit()
    return MessageResponse(message="Student details updated successfully")


# ── Franchise IB Wallet & Withdrawal Routes ─────────────────────────

from fastapi import File, Form, UploadFile
from typing import Optional, List
import os
from uuid import uuid4

def withdrawal_resp(req) -> schemas.FranchiseIBWithdrawalResponse:
    fib_name = None
    if hasattr(req, "franchise_ib") and req.franchise_ib and req.franchise_ib.user:
        fib_name = req.franchise_ib.user.full_name
    return schemas.FranchiseIBWithdrawalResponse(
        id=req.id,
        franchise_ib_id=req.franchise_ib_id,
        franchise_ib_name=fib_name,
        amount=req.amount,
        withdrawal_method=req.withdrawal_method,
        account_holder_name=req.account_holder_name,
        bank_name=req.bank_name,
        account_number=req.account_number,
        ifsc_code=req.ifsc_code,
        upi_id=req.upi_id,
        qr_code_image=req.qr_code_image,
        status=req.status,
        requested_at=req.requested_at,
        approved_at=req.approved_at,
        paid_at=req.paid_at,
        admin_remarks=req.admin_remarks,
        payment_proof=req.payment_proof,
        utr_number=req.utr_number,
        transaction_reference=req.transaction_reference,
    )


@router.get("/wallet", response_model=schemas.FranchiseIBWalletSummary)
async def get_franchise_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    summary = await services.get_franchise_wallet_summary(db, profile.id)
    return summary


@router.get("/withdrawals", response_model=List[schemas.FranchiseIBWithdrawalResponse])
async def get_franchise_withdrawals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    reqs = await services.list_franchise_withdrawals(db, profile.id)
    return [withdrawal_resp(r) for r in reqs]


@router.post("/withdrawals", response_model=schemas.FranchiseIBWithdrawalResponse)
async def create_franchise_withdrawal(
    body: schemas.FranchiseIBWithdrawalCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    req = await services.create_franchise_withdrawal(db, profile.id, body.model_dump())
    await db.commit()
    reqs = await services.list_franchise_withdrawals(db, profile.id)
    return withdrawal_resp(next(r for r in reqs if r.id == req.id))


@router.post("/withdrawals/qr-upload")
async def upload_franchise_qr(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if ext not in {"jpg", "jpeg", "png"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: jpg, jpeg, png")
    upload_dir = os.path.join("uploads", "withdrawal_qr")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as out:
        out.write(content)
    return {"url": f"/{path.replace(os.sep, '/')}"}


# ── Admin Franchise IB Withdrawal Management ───────────────────────

@router.get("/admin/withdrawals", response_model=List[schemas.FranchiseIBWithdrawalResponse])
async def admin_list_franchise_withdrawals(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    reqs = await services.list_franchise_withdrawals(db, franchise_ib_id=None)
    return [withdrawal_resp(r) for r in reqs]


@router.post("/admin/withdrawals/{request_id}/approve", response_model=schemas.FranchiseIBWithdrawalResponse)
async def admin_approve_franchise_withdrawal(
    request_id: int,
    remarks: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    req = await services.approve_franchise_withdrawal(db, request_id, remarks)
    await db.commit()
    reqs = await services.list_franchise_withdrawals(db, None)
    return withdrawal_resp(next(r for r in reqs if r.id == req.id))


@router.post("/admin/withdrawals/{request_id}/reject", response_model=schemas.FranchiseIBWithdrawalResponse)
async def admin_reject_franchise_withdrawal(
    request_id: int,
    remarks: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    req = await services.reject_franchise_withdrawal(db, request_id, remarks)
    await db.commit()
    reqs = await services.list_franchise_withdrawals(db, None)
    return withdrawal_resp(next(r for r in reqs if r.id == req.id))


@router.post("/admin/withdrawals/{request_id}/mark-paid", response_model=schemas.FranchiseIBWithdrawalResponse)
async def admin_mark_paid_franchise_withdrawal(
    request_id: int,
    utr_number: Optional[str] = Form(None),
    transaction_reference: Optional[str] = Form(None),
    proof_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    proof_path = None
    if proof_file:
        ext = os.path.splitext(proof_file.filename or "")[1].lower().lstrip(".")
        if ext not in {"pdf", "jpg", "jpeg", "png"}:
            raise HTTPException(status_code=400, detail="Unsupported file type for proof")
        upload_dir = os.path.join("uploads", "commission_proofs")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid4().hex}.{ext}"
        path = os.path.join(upload_dir, filename)
        content = await proof_file.read()
        with open(path, "wb") as out:
            out.write(content)
        proof_path = f"/{path.replace(os.sep, '/')}"

    req = await services.mark_paid_franchise_withdrawal(
        db, request_id, proof_path, utr_number, transaction_reference
    )
    await db.commit()
    reqs = await services.list_franchise_withdrawals(db, None)
    return withdrawal_resp(next(r for r in reqs if r.id == req.id))


