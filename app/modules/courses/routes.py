"""Courses module — API routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File
import os
import uuid
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
    is_featured: Optional[bool] = Query(None, description="Filter by featured status"),
    db: AsyncSession = Depends(get_db),
):
    """List all published courses. Use ?is_featured=true for landing page."""
    courses = await services.list_courses(db, skip=pagination.skip, limit=pagination.limit, is_featured=is_featured)
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
    try:
        from app.modules.batches.services import enroll_student_in_batch_or_active
        await enroll_student_in_batch_or_active(
            db,
            user_id=current_user.id,
            course_id=course_id,
            batch_id=body.batch_id,
            price_paid=enrollment.price_paid or 0.0
        )
    except Exception as batch_err:
        import logging
        logging.getLogger(__name__).error(f"Free enrollment batch auto-enroll failed: {batch_err}")
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

# ── Assignments ──────────────────────────────────────────────────────
@router.get("/assignments/my-submissions", response_model=List[schemas.AssignmentSubmissionResponse])
async def get_my_submissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all assignment submissions for the current student."""
    submissions = await services.get_user_assignment_submissions(db, current_user.id)
    return [schemas.AssignmentSubmissionResponse.model_validate(s) for s in submissions]

@router.get("/{course_id}/assignments", response_model=List[schemas.AssignmentResponse])
async def get_course_assignments(
    course_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all assignments for a course."""
    assignments = await services.get_course_assignments(db, course_id)
    return [schemas.AssignmentResponse.model_validate(a) for a in assignments]

@router.post("/assignments/submit", response_model=schemas.AssignmentSubmissionResponse, status_code=201)
async def submit_assignment(
    body: schemas.AssignmentSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Student submits an assignment file."""
    submission = await services.submit_assignment(db, body.model_dump(), current_user.id)
    return schemas.AssignmentSubmissionResponse.model_validate(submission)

@router.post("/assignments/upload", response_model=dict, status_code=201)
async def upload_assignment_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Student or Faculty uploads an assignment file."""
    os.makedirs("uploads/assignments", exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_name = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join("uploads/assignments", unique_name)
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
        
    return {
        "url": f"/uploads/assignments/{unique_name}",
        "original_name": file.filename,
        "content_type": file.content_type or "application/octet-stream"
    }


@router.get("/admin/{course_id}/day-tasks", tags=["Admin"])
async def admin_get_course_day_tasks(
    course_id: int,
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from app.modules.batches.models import BatchDayTask
    
    result = await db.execute(
        select(BatchDayTask)
        .where(BatchDayTask.course_id == course_id, BatchDayTask.batch_id.is_(None))
        .order_by(BatchDayTask.day_number)
    )
    return result.scalars().all()


@router.post("/admin/{course_id}/day-tasks", tags=["Admin"])
async def admin_create_course_day_task(
    course_id: int,
    payload: dict,  
    db: AsyncSession = Depends(get_db)
):
    from app.modules.batches.models import BatchDayTask
    import dateutil.parser
    
    # Process datetimes
    start_time = payload.get("start_time")
    if start_time: start_time = dateutil.parser.isoparse(start_time)
    end_time = payload.get("end_time")
    if end_time: end_time = dateutil.parser.isoparse(end_time)

    task = BatchDayTask(
        course_id=course_id,
        batch_id=None,
        day_number=payload.get("day_number", 1),
        title=payload.get("title", ""),
        content_type=payload.get("content_type", "text"),
        content=payload.get("content"),
        duration_minutes=payload.get("duration_minutes"),
        start_time=start_time,
        end_time=end_time,
        instructor_name=payload.get("instructor_name"),
        exam_title=payload.get("exam_title"),
        exam_passing_score=payload.get("exam_passing_score"),
        linked_assignment_id=payload.get("linked_assignment_id"),
        is_published=payload.get("is_published", False)
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task
