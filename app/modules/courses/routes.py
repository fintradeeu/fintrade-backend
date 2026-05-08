"""Courses module — API routes."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams
from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.courses import schemas, services
from app.modules.auth.models import User

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("", response_model=List[schemas.CourseListResponse])
async def list_courses(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """List all published courses."""
    courses = await services.list_courses(db, skip=pagination.skip, limit=pagination.limit)
    return [schemas.CourseListResponse.model_validate(c) for c in courses]


@router.get("/enrolled", response_model=List[schemas.EnrollmentResponse])
async def enrolled_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get courses the current user is enrolled in."""
    enrollments = await services.get_enrolled_courses(db, current_user.id)
    return [schemas.EnrollmentResponse.model_validate(e) for e in enrollments]


@router.get("/{course_id}", response_model=schemas.CourseDetailResponse)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full course details with modules and lessons."""
    course = await services.get_course(db, course_id)
    return schemas.CourseDetailResponse.model_validate(course)


@router.post("/{course_id}/enroll", response_model=schemas.EnrollmentResponse)
async def enroll(
    course_id: int,
    body: schemas.EnrollRequest = schemas.EnrollRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enroll the current user in a course. Optionally provide a distributor referral code."""
    enrollment = await services.enroll_user(
        db, current_user.id, course_id, distributor_code=body.distributor_code
    )
    # Re-fetch with course relationship loaded
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.courses.models import CourseEnrollment
    result = await db.execute(
        select(CourseEnrollment)
        .options(selectinload(CourseEnrollment.course))
        .where(CourseEnrollment.id == enrollment.id)
    )
    enrollment = result.scalar_one()
    return schemas.EnrollmentResponse.model_validate(enrollment)

@router.post("/lessons/{lesson_id}/audio")
async def generate_audio(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate audio from a text lesson (mock implementation)."""
    import asyncio
    await asyncio.sleep(1) # Simulate processing
    return {
        "status": "success",
        "audio_url": f"https://example.com/audio/lesson_{lesson_id}.mp3",
        "message": "Audio generated successfully."
    }
