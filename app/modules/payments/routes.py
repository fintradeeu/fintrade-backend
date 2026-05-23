"""Payments module — API routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

from app.db.database import get_db
from app.core.security import get_current_user
from app.modules.auth.models import User
from app.modules.payments import schemas, services

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/create", response_model=schemas.PaymentInitiateResponse)
async def create_payment(
    body: schemas.PaymentInitiateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a course payment via Easebuzz."""
    return await services.initiate_payment(db, user=current_user, course_id=body.course_id, base_url=str(request.base_url))

@router.post("/success")
async def payment_success_redirect(request: Request, db: AsyncSession = Depends(get_db)):
    """Easebuzz redirects here on success via POST."""
    form_data = await request.form()
    form_dict = dict(form_data)
    
    # Process it just like a webhook (idempotent, safe fallback for localhost)
    await services.process_webhook(db, form_data=form_dict)
    
    txnid = form_data.get("txnid", "")
    frontend_url = settings.CORS_ORIGINS.split(',')[0]
    return RedirectResponse(url=f"{frontend_url}/payment/success?txnid={txnid}", status_code=303)

@router.post("/failure")
async def payment_failure_redirect(request: Request, db: AsyncSession = Depends(get_db)):
    """Easebuzz redirects here on failure/cancel via POST."""
    form_data = await request.form()
    form_dict = dict(form_data)
    
    # Process it just like a webhook (idempotent, safe fallback for localhost)
    await services.process_webhook(db, form_data=form_dict)

    txnid = form_data.get("txnid", "")
    frontend_url = settings.CORS_ORIGINS.split(',')[0]
    return RedirectResponse(url=f"{frontend_url}/payment/failure?txnid={txnid}", status_code=303)

@router.post("/webhook")
async def easebuzz_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Receive and process Easebuzz payment webhook."""
    # Webhooks come as form-urlencoded data
    form_data = await request.form()
    # Convert immutable FormData to dict
    form_dict = dict(form_data)
    
    return await services.process_webhook(db, form_data=form_dict)

