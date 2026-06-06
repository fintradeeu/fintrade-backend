"""Lectures module - API routes."""

from typing import List, Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
# pyrefly: ignore [missing-import]
from app.modules.auth.models import User
from app.modules.lectures import schemas, services

router = APIRouter(prefix="/lectures", tags=["Lectures"])


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


@router.post("/send-otp", response_model=schemas.MessageResponse)
async def send_registration_otp(
    data: schemas.RegistrationOTPSend,
    db: AsyncSession = Depends(get_db),
):
    """Send an OTP code to verify the email for registration."""
    await services.send_registration_otp(db, email=data.email, lecture_title=data.lecture_title)
    return schemas.MessageResponse(message="OTP sent successfully.")


@router.post("/register", response_model=schemas.LectureRegistrationResponse)
async def register_live_class(
    data: schemas.LectureRegistrationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register for a live class. Public endpoint with OTP verification."""
    registration = await services.register_for_lecture_with_otp(db, data.model_dump(exclude_unset=True))
    return schemas.LectureRegistrationResponse.model_validate(registration)
