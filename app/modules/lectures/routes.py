"""Lectures module - API routes."""

import random
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.lectures import schemas, services

router = APIRouter(prefix="/lectures", tags=["Lectures"])

_lecture_otps: dict = {}


class SendOTPRequest(BaseModel):
    email: str
    lecture_title: str | None = None


@router.get("", response_model=List[schemas.LectureResponse])
async def list_lectures(
    course_id: Optional[int] = Query(None, description="Filter by course"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    lectures = await services.list_lectures(db, course_id=course_id, skip=skip, limit=limit)
    return [schemas.LectureResponse.model_validate(l) for l in lectures]


@router.post("/join", response_model=schemas.LectureJoinResponse)
async def join_lecture(
    lecture_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await services.join_lecture(db, current_user.id, lecture_id)
    return schemas.LectureJoinResponse(**result)


@router.post("/register", response_model=schemas.LectureRegistrationResponse)
async def register_live_class(
    data: schemas.LectureRegistrationCreate,
    db: AsyncSession = Depends(get_db),
):
    registration = await services.register_for_lecture(db, data.model_dump(exclude_unset=True))
    return schemas.LectureRegistrationResponse.model_validate(registration)


@router.post("/send-otp")
async def send_lecture_otp(data: SendOTPRequest):
    from app.utils.smtp_notifications import send_email, build_otp_email_html
    code = str(random.randint(100000, 999999))
    _lecture_otps[data.email] = {"code": code, "expires_at": time.time() + 300}
    subject = "{} - Your FinTrade Verification Code".format(code)
    html = build_otp_email_html(code, data.email)
    await send_email(to_email=data.email, subject=subject, body_html=html)
    return {"message": "OTP sent successfully"}
