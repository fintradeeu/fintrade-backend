"""Faculty module — API routes (faculty role)."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.courses.schemas import CourseDetailResponse, LessonCreate, LessonResponse
from app.modules.lectures.schemas import LectureCreate, LectureResponse, RecordingCreate, RecordingResponse
from app.modules.faculty import schemas, services

router = APIRouter(prefix="/faculty", tags=["Faculty"])


@router.get("/courses", response_model=List[CourseDetailResponse])
async def list_my_courses(
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List courses created by this faculty member."""
    courses = await services.get_faculty_courses(db, current_user.id)
    return [CourseDetailResponse.model_validate(c) for c in courses]


@router.post("/lessons/upload", response_model=LessonResponse, status_code=201)
async def upload_lesson(
    body: LessonCreate,
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a lesson in a module (faculty must own the parent course)."""
    lesson = await services.create_faculty_lesson(db, body.model_dump(), current_user.id)
    return LessonResponse.model_validate(lesson)


@router.post("/lectures/create", response_model=LectureResponse, status_code=201)
async def create_lecture(
    body: LectureCreate,
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a new lecture (faculty is automatically set as instructor)."""
    import traceback
    try:
        lecture = await services.create_faculty_lecture(db, body.model_dump(), current_user.id)
        return LectureResponse.model_validate(lecture)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@router.post("/lectures/{lecture_id}/complete", response_model=LectureResponse)
async def complete_lecture(
    lecture_id: int,
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Mark a lecture as completed manually."""
    lecture = await services.complete_lecture(db, lecture_id, current_user.id)
    return LectureResponse.model_validate(lecture)

@router.post("/lectures/{lecture_id}/recordings", response_model=RecordingResponse, status_code=201)
async def upload_recording(
    lecture_id: int,
    body: RecordingCreate,
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Save a recording to a lecture."""
    recording = await services.add_lecture_recording(db, lecture_id, body.model_dump(), current_user.id)
    return RecordingResponse.model_validate(recording)


@router.get("/students", response_model=List[schemas.FacultyStudentResponse])
async def list_students(
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List students enrolled in courses created by this faculty."""
    students = await services.get_faculty_students(db, current_user.id)
    return [schemas.FacultyStudentResponse(**s) for s in students]


@router.get("/reports", response_model=schemas.FacultyReportsResponse)
async def get_faculty_reports(
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated performance reports for the faculty member's courses and students."""
    reports = await services.get_faculty_reports(db, current_user.id)
    return schemas.FacultyReportsResponse(**reports)

@router.get("/students/{student_id}/progress")
async def get_student_progress(
    student_id: int,
    current_user: User = Depends(require_roles(["faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed progress of a specific student."""
    from app.modules.learning.progress import get_student_progress_details
    return await get_student_progress_details(db, student_id)
