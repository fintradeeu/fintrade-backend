"""Certificates module — API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.certificates import schemas, services

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.post("/generate", response_model=schemas.CertificateResponse, status_code=201)
async def generate_certificate(
    req: schemas.CertificateGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a certificate after completing a course."""
    cert = await services.generate_certificate(db, current_user.id, req.course_id)
    return schemas.CertificateResponse.model_validate(cert)

@router.get("", response_model=list[schemas.CertificateResponse])
async def list_user_certificates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all certificates for the currently logged-in student."""
    certs = await services.list_certificates_for_user(db, current_user.id)
    return [schemas.CertificateResponse.model_validate(c) for c in certs]


@router.get("/{cert_id}", response_model=schemas.CertificateResponse)
async def get_certificate(
    cert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """View certificate metadata."""
    cert = await services.get_certificate(db, cert_id, current_user.id)
    return schemas.CertificateResponse.model_validate(cert)


@router.get("/download/{cert_id}")
async def download_certificate(
    cert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download certificate PDF."""
    file_path = await services.get_certificate_for_download(db, cert_id, current_user.id)
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate_{cert_id}.pdf",
    )
