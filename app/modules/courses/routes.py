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
    """Generate audio from a text lesson."""
    import os
    from bs4 import BeautifulSoup
    from gtts import gTTS
    from fastapi import HTTPException, status
    from sqlalchemy import select
    from app.modules.courses.models import Lesson

    # Fetch lesson
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    
    if lesson.content_type != "text":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only text lessons can be converted to audio.")
    
    if not lesson.content or not str(lesson.content).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lesson has no text content to convert.")

    # Strip HTML tags
    soup = BeautifulSoup(lesson.content, "html.parser")
    clean_text = soup.get_text(separator=" ", strip=True)

    if not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lesson content is empty after removing formatting.")

    # Generate audio
    audio_dir = "uploads/audio"
    os.makedirs(audio_dir, exist_ok=True)
    file_name = f"lesson_{lesson_id}.mp3"
    file_path = os.path.join(audio_dir, file_name)
    audio_url = f"/uploads/audio/{file_name}"

    try:
        tts = gTTS(clean_text, lang='en')
        tts.save(file_path)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate audio: {str(e)}")

    # Save url to database so we don't have to generate it again
    lesson.video_url = audio_url
    await db.commit()

    return {
        "status": "success",
        "audio_url": audio_url,
        "message": "Audio generated successfully."
    }
