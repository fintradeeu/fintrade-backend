"""IB commission and wallet API routes."""

import os
from uuid import uuid4
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.commissions import schemas, services
from app.modules.distributors.services import get_distributor_by_user_id

router = APIRouter(tags=["IB Commission Management"])


def require_super_admin(user: User) -> None:
    if not any(role.name == "super_admin" for role in user.roles):
        raise HTTPException(status_code=403, detail="Requires Super Admin role")


def withdrawal_response(req) -> schemas.WithdrawalResponse:
    return schemas.WithdrawalResponse(
        id=req.id,
        ib_id=req.ib_id,
        ib_name=req.ib.user.full_name if req.ib and req.ib.user else None,
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
    )


def tx_response(tx) -> schemas.WalletTransactionResponse:
    return schemas.WalletTransactionResponse(
        id=tx.id,
        ib_id=tx.ib_id,
        student_name=tx.student.full_name if tx.student else None,
        course_title=tx.course.title if tx.course else None,
        commission_amount=tx.commission_amount,
        transaction_type=tx.transaction_type,
        description=tx.description,
        reference_no=tx.reference_no,
        status=tx.status,
        balance_after=tx.balance_after,
        created_at=tx.created_at,
    )


async def save_upload(file: UploadFile, folder: str, allowed: set[str]) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}")
    upload_dir = os.path.join("uploads", folder)
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as out:
        out.write(content)
    return f"/{path.replace(os.sep, '/')}"


@router.get("/admin/commissions/courses", response_model=List[schemas.CourseCommissionSummary])
async def commission_courses(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return await services.list_commission_courses(db)


@router.get("/admin/commissions/courses/{course_id}/ibs", response_model=List[schemas.IBCommissionRow])
async def course_ib_commissions(
    course_id: int,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return await services.list_ib_commissions_for_course(db, course_id)


@router.put("/admin/commissions/courses/{course_id}/ibs/{ib_id}", response_model=schemas.IBCommissionRow)
async def upsert_commission(
    course_id: int,
    ib_id: int,
    body: schemas.CommissionUpsertRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    commission = await services.upsert_course_ib_commission(
        db, course_id, ib_id, body.commission_type, body.commission_value, body.is_active, admin.id
    )
    await db.commit()
    rows = await services.list_ib_commissions_for_course(db, course_id)
    return next(row for row in rows if row["ib_id"] == commission.ib_id)


@router.patch("/admin/commissions/{commission_id}/status")
async def commission_status(
    commission_id: int,
    is_active: bool,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    await services.set_commission_status(db, commission_id, is_active, admin.id)
    await db.commit()
    return {"message": "Commission status updated"}


@router.get("/admin/commissions/wallet-transactions", response_model=List[schemas.WalletTransactionResponse])
async def admin_wallet_transactions(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return [tx_response(tx) for tx in await services.list_wallet_transactions(db)]


@router.get("/admin/commissions/withdrawals", response_model=List[schemas.WithdrawalResponse])
async def admin_withdrawals(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return [withdrawal_response(req) for req in await services.list_withdrawals(db)]


@router.post("/admin/commissions/withdrawals/{withdrawal_id}/approve", response_model=schemas.WithdrawalResponse)
async def approve_withdrawal(
    withdrawal_id: int,
    body: schemas.WithdrawalActionRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    req = await services.approve_withdrawal(db, withdrawal_id, admin.id, body.admin_remarks)
    await db.commit()
    reqs = await services.list_withdrawals(db)
    return withdrawal_response(next(r for r in reqs if r.id == req.id))


@router.post("/admin/commissions/withdrawals/{withdrawal_id}/reject", response_model=schemas.WithdrawalResponse)
async def reject_withdrawal(
    withdrawal_id: int,
    body: schemas.WithdrawalActionRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    req = await services.reject_withdrawal(db, withdrawal_id, admin.id, body.admin_remarks)
    await db.commit()
    reqs = await services.list_withdrawals(db)
    return withdrawal_response(next(r for r in reqs if r.id == req.id))


@router.post("/admin/commissions/withdrawals/{withdrawal_id}/mark-paid", response_model=schemas.WithdrawalResponse)
async def mark_paid(
    withdrawal_id: int,
    utr_number: Optional[str] = Form(None),
    transaction_reference: Optional[str] = Form(None),
    proof_file: Optional[UploadFile] = File(None),
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    proof_path = await save_upload(proof_file, "commission_proofs", {"pdf", "jpg", "jpeg", "png"}) if proof_file else None
    req = await services.mark_withdrawal_paid(db, withdrawal_id, admin.id, proof_path, utr_number, transaction_reference)
    await db.commit()
    reqs = await services.list_withdrawals(db)
    return withdrawal_response(next(r for r in reqs if r.id == req.id))


@router.get("/admin/commissions/reports/commission", response_model=schemas.CommissionReport)
async def admin_commission_report(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return await services.commission_report(db)


@router.get("/admin/commissions/reports/withdrawals", response_model=schemas.WithdrawalReport)
async def admin_withdrawal_report(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    require_super_admin(admin)
    return await services.withdrawal_report(db)


@router.get("/distributor/wallet", response_model=schemas.WalletSummary)
async def ib_wallet(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    ib = await get_distributor_by_user_id(db, current_user.id)
    return await services.wallet_summary(db, ib.id)


@router.get("/distributor/wallet/transactions", response_model=List[schemas.WalletTransactionResponse])
async def ib_wallet_transactions(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    ib = await get_distributor_by_user_id(db, current_user.id)
    return [tx_response(tx) for tx in await services.list_wallet_transactions(db, ib.id)]


@router.post("/distributor/withdrawals", response_model=schemas.WithdrawalResponse)
async def create_ib_withdrawal(
    body: schemas.WithdrawalCreateRequest,
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    ib = await get_distributor_by_user_id(db, current_user.id)
    req = await services.create_withdrawal(db, ib.id, body.model_dump())
    await db.commit()
    reqs = await services.list_withdrawals(db, ib.id)
    return withdrawal_response(next(r for r in reqs if r.id == req.id))


@router.post("/distributor/withdrawals/qr-upload")
async def upload_qr_code(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles(["distributor"])),
):
    return {"url": await save_upload(file, "withdrawal_qr", {"jpg", "jpeg", "png"})}


@router.get("/admin/commissions/revenue/ib-wise")
async def ib_wise_revenue(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Return per-Franchise-IB revenue breakdown for superadmin."""
    require_super_admin(admin)
    return await services.ib_wise_revenue_report(db)


@router.get("/distributor/withdrawals", response_model=List[schemas.WithdrawalResponse])
async def ib_withdrawals(
    current_user: User = Depends(require_roles(["distributor"])),
    db: AsyncSession = Depends(get_db),
):
    ib = await get_distributor_by_user_id(db, current_user.id)
    return [withdrawal_response(req) for req in await services.list_withdrawals(db, ib.id)]
