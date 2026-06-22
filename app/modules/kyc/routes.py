"""KYC module — API routes."""

from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.kyc import schemas, services

router = APIRouter(prefix="/kyc", tags=["KYC & Contracts"])


# ── Student endpoints ───────────────────────────────────────────────

@router.post("/submit", response_model=schemas.KYCStatusResponse, status_code=201)
async def submit_kyc(
    body: schemas.KYCSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit or update KYC personal details."""
    kyc = await services.submit_kyc(db, current_user.id, body.model_dump(exclude_unset=True))
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.get("/status", response_model=schemas.KYCStatusResponse)
async def kyc_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's KYC status."""
    kyc = await services.get_kyc_status(db, current_user.id)
    if not kyc:
        return schemas.KYCStatusResponse(
            id=0, user_id=current_user.id, full_name=current_user.full_name, status="not_started"
        )
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.post("/send-mobile-otp", response_model=schemas.MessageResponse)
async def send_mobile_otp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a real SMS OTP via Twilio Verify to the user's KYC mobile number."""
    await services.send_mobile_otp(db, current_user.id)
    return schemas.MessageResponse(message="Mobile OTP sent successfully via SMS")


@router.post("/verify-mobile-otp", response_model=schemas.MessageResponse)
async def verify_mobile_otp(
    body: schemas.OTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify mobile OTP using Twilio Verify API."""
    await services.verify_otp(db, current_user.id, "mobile", body.otp)
    return schemas.MessageResponse(message="Mobile OTP verified successfully")


@router.post("/verify-email-otp", response_model=schemas.MessageResponse)
async def verify_email_otp(
    body: schemas.OTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify email OTP (demo mode)."""
    await services.verify_otp(db, current_user.id, "email", body.otp)
    return schemas.MessageResponse(message="Email OTP verified successfully")


@router.post("/send-email-otp", response_model=schemas.MessageResponse)
async def send_email_otp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and send an email OTP to the user's registered email address."""
    await services.send_email_otp(db, current_user)
    return schemas.MessageResponse(message="Email OTP sent successfully via email")


@router.post("/upload-document", response_model=schemas.KYCStatusResponse)
async def upload_document(
    doc_type: str = Query(..., description="One of: aadhaar, pan, photo"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload KYC document (aadhaar, pan, photo)."""
    kyc = await services.upload_document(db, current_user.id, doc_type, file)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.post("/upload-signature", response_model=schemas.KYCStatusResponse)
async def upload_signature(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload digital signature."""
    kyc = await services.upload_document(db, current_user.id, "signature", file)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.post("/upload-biometric", response_model=schemas.KYCStatusResponse)
async def upload_biometric(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload biometric selfie."""
    kyc = await services.upload_document(db, current_user.id, "biometric", file)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.post("/generate-contract", response_model=schemas.ContractResponse, status_code=201)
async def generate_contract(
    body: schemas.ContractGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a complete KYC contract dossier for admin review."""
    contract = await services.generate_contract(
        db, current_user.id, body.course_id, body.terms_accepted
    )
    return schemas.ContractResponse.model_validate(contract)


@router.get("/contract", response_model=schemas.ContractResponse)
async def get_contract(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's contract."""
    contract = await services.get_user_contract(db, current_user.id)
    if not contract:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No contract found")
    return schemas.ContractResponse.model_validate(contract)


# ── Admin endpoints ─────────────────────────────────────────────────

@router.get("/admin/submissions", response_model=List[schemas.AdminKYCListItem])
async def list_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all KYC submissions (admin only)."""
    submissions = await services.list_kyc_submissions(db, skip, limit)
    return [schemas.AdminKYCListItem.model_validate(s) for s in submissions]


@router.get("/admin/submissions/{kyc_id}", response_model=schemas.KYCStatusResponse)
async def get_submission(
    kyc_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """View specific KYC submission (admin only)."""
    kyc = await services.get_kyc_detail(db, kyc_id)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.get("/admin/user/{user_id}", response_model=schemas.KYCStatusResponse)
async def get_user_kyc_detail(
    user_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get full KYC details for a specific user by user_id (admin only)."""
    from fastapi import HTTPException
    kyc = await services.get_kyc_status(db, user_id)
    if not kyc:
        raise HTTPException(status_code=404, detail="No KYC submission found for this user.")
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.put("/admin/submissions/{kyc_id}/approve", response_model=schemas.KYCStatusResponse)
async def approve_submission(
    kyc_id: int,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Approve KYC submission (admin only)."""
    kyc = await services.approve_kyc(db, kyc_id, admin.id)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.put("/admin/submissions/{kyc_id}/reject", response_model=schemas.KYCStatusResponse)
async def reject_submission(
    kyc_id: int,
    body: schemas.KYCRejectRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Reject KYC submission with reason (admin only)."""
    kyc = await services.reject_kyc(db, kyc_id, admin.id, body.reason)
    return schemas.KYCStatusResponse.model_validate(kyc)


@router.get("/admin/contracts", response_model=List[schemas.AdminContractListItem])
async def list_contracts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all contracts (admin only)."""
    contracts = await services.list_contracts(db, skip, limit)
    items = []
    for c in contracts:
        # Get KYC status for each contract
        kyc = await services.get_kyc_detail(db, c.kyc_id)
        
        course_title = None
        if c.course_id:
            from app.modules.courses.models import Course
            course_res = await db.execute(select(Course).where(Course.id == c.course_id))
            course_obj = course_res.scalar_one_or_none()
            if course_obj:
                course_title = course_obj.title
                
        items.append(schemas.AdminContractListItem(
            id=c.id,
            kyc_id=c.kyc_id,
            contract_number=c.contract_number,
            user_id=c.user_id,
            user_name=c.user.full_name if c.user else None,
            user_email=c.user.email if c.user else None,
            user_mobile=kyc.mobile if kyc else None,
            user_aadhaar=kyc.aadhaar_number if kyc else None,
            user_pan=kyc.pan_number if kyc else None,
            user_dob=kyc.dob if kyc else None,
            user_qualification=kyc.qualification if kyc else None,
            user_address=kyc.address if kyc else None,
            aadhaar_doc_url=kyc.aadhaar_doc_url if kyc else None,
            pan_doc_url=kyc.pan_doc_url if kyc else None,
            photo_url=kyc.photo_url if kyc else None,
            signature_url=kyc.signature_url if kyc else None,
            biometric_selfie_url=kyc.biometric_selfie_url if kyc else None,
            kyc_status=kyc.status if kyc else None,
            rejection_reason=kyc.rejection_reason if kyc else None,
            course_id=c.course_id,
            course_title=course_title,
            signed_at=c.signed_at,
            created_at=c.created_at,
        ))
    return items


@router.get("/admin/contracts/{contract_id}/download")
async def download_contract(
    contract_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Download contract text (admin only)."""
    contract = await services.get_contract_detail(db, contract_id)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=contract.contract_text or "No contract content available",
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={contract.contract_number}.txt"},
    )
