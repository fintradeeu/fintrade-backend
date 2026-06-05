"""Lectures module — API routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
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
    """List scheduled lectures."""
    lectures = await services.list_lectures(db, course_id=course_id, skip=skip, limit=limit)
    return [schemas.LectureResponse.model_validate(l) for l in lectures]


@router.post("/join", response_model=schemas.LectureJoinResponse)
async def join_lecture(
    lecture_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a lecture and get the meeting link."""
    result = await services.join_lecture(db, current_user.id, lecture_id)
    return schemas.LectureJoinResponse(**result)


@router.post("/register", response_model=schemas.LectureRegistrationResponse)
async def register_live_class(
    data: schemas.LectureRegistrationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register for a live class. Public endpoint."""
    # We could try to extract user_id if we have an optional current_user,
    # but since this is a public form we will just accept the data.
    registration = await services.register_for_lecture(db, data.model_dump(exclude_unset=True))
    return schemas.LectureRegistrationResponse.model_validate(registration)
