from typing import List, Optional
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from sqlalchemy import select
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.batches import schemas, services

router = APIRouter(prefix="/batches", tags=["Batch Management"])


@router.get("/public/list", response_model=List[schemas.BatchResponse])
async def get_active_batches_for_course(
    course_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all open/upcoming registration batches for a given course or all if course_id is omitted."""
    now = datetime.now(timezone.utc)
    from app.modules.batches.models import Batch, BatchCourse
    from sqlalchemy.orm import joinedload
    
    stmt = (
        select(Batch)
        .options(joinedload(Batch.courses).joinedload(BatchCourse.course))
        .where(
            Batch.is_active == True,
            Batch.is_published == True
        )
        .order_by(Batch.start_date.asc())
    )
    
    if course_id is not None:
        stmt = stmt.join(BatchCourse, BatchCourse.batch_id == Batch.id).where(BatchCourse.course_id == course_id)
        
    batch_res = await db.execute(stmt)
    batches = list(batch_res.scalars().unique().all())
    
    from app.modules.batches.services import update_batch_status_based_on_dates
    for b in batches:
        calculated_status = update_batch_status_based_on_dates(b)
        if b.status != calculated_status:
            b.status = calculated_status
    await db.commit()
    return [schemas.BatchResponse.model_validate(b) for b in batches]



# ── Student endpoints ───────────────────────────────────────────────

@router.get("/student/current", response_model=schemas.BatchResponse)
async def get_my_batch(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of the logged-in student's active batch."""
    batch = await services.get_student_current_batch(db, current_user.id)
    if not batch:
        raise HTTPException(status_code=404, detail="No active batch enrollment found.")
    return schemas.BatchResponse.model_validate(batch)


@router.get("/student/dashboard", response_model=schemas.BatchDashboardResponse)
async def get_my_batch_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details, countdown, locking, and course list for the student's batch."""
    data = await services.get_student_batch_dashboard(db, current_user.id)
    return schemas.BatchDashboardResponse(**data)


# ── Admin endpoints ─────────────────────────────────────────────────

@router.get("/student/courses/{course_id}/structure", response_model=List[schemas.BatchModuleResponse])
async def get_my_batch_course_structure(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the logged-in student's batch-specific modules and lessons for a course."""
    modules = await services.list_student_batch_modules(db, current_user.id, course_id)
    return [schemas.BatchModuleResponse.model_validate(m) for m in modules]


@router.post("/student/lessons/{lesson_id}/complete", response_model=dict)
async def complete_my_batch_lesson(
    lesson_id: int,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a batch-specific lesson completed without touching the template course lesson."""
    course_id = body.get("course_id")
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id is required")
    success = await services.mark_batch_lesson_completed(db, current_user.id, int(course_id), lesson_id)
    return {"status": "success", "completed": success}


@router.get("/student/lectures", response_model=List[schemas.BatchLectureResponse])
async def get_my_batch_lectures(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lectures = await services.list_student_batch_lectures(db, current_user.id)
    return [schemas.BatchLectureResponse.model_validate(l) for l in lectures]


@router.get("/student/assignments", response_model=List[schemas.BatchAssignmentResponse])
async def get_my_batch_assignments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignments = await services.list_student_batch_assignments(db, current_user.id)
    return [schemas.BatchAssignmentResponse.model_validate(a) for a in assignments]


@router.get("/student/assignments/my-submissions", response_model=List[schemas.BatchAssignmentSubmissionResponse])
async def get_my_batch_assignment_submissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submissions = await services.get_user_batch_assignment_submissions(db, current_user.id)
    return [schemas.BatchAssignmentSubmissionResponse.model_validate(s) for s in submissions]


@router.post("/student/assignments/submit", response_model=schemas.BatchAssignmentSubmissionResponse, status_code=201)
async def submit_my_batch_assignment(
    body: schemas.BatchAssignmentSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await services.submit_batch_assignment(
        db,
        user_id=current_user.id,
        assignment_id=body.batch_assignment_id,
        file_url=body.file_url,
    )
    return schemas.BatchAssignmentSubmissionResponse.model_validate(submission)


@router.get("/admin/lectures", response_model=List[schemas.BatchLectureResponse])
async def admin_list_batch_lectures(
    batch_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    lectures = await services.list_batch_lectures(db, batch_id=batch_id, course_id=course_id)
    return [schemas.BatchLectureResponse.model_validate(l) for l in lectures]


@router.post("/admin/lectures", response_model=schemas.BatchLectureResponse, status_code=201)
async def admin_create_batch_lecture(
    body: schemas.BatchLectureCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    lecture = await services.create_batch_lecture(db, body.model_dump())
    return schemas.BatchLectureResponse.model_validate(lecture)


@router.put("/admin/lectures/{lecture_id}", response_model=schemas.BatchLectureResponse)
async def admin_update_batch_lecture(
    lecture_id: int,
    body: schemas.BatchLectureUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    lecture = await services.update_batch_lecture(db, lecture_id, body.model_dump(exclude_unset=True))
    return schemas.BatchLectureResponse.model_validate(lecture)


@router.delete("/admin/lectures/{lecture_id}", response_model=dict)
async def admin_delete_batch_lecture(
    lecture_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    success = await services.delete_batch_lecture(db, lecture_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch lecture not found")
    return {"message": "Batch lecture deleted successfully"}


@router.get("/admin/assignments", response_model=List[schemas.BatchAssignmentResponse])
async def admin_list_batch_assignments(
    batch_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    assignments = await services.list_batch_assignments(db, batch_id=batch_id, course_id=course_id)
    return [schemas.BatchAssignmentResponse.model_validate(a) for a in assignments]


@router.post("/admin/assignments", response_model=schemas.BatchAssignmentResponse, status_code=201)
async def admin_create_batch_assignment(
    body: schemas.BatchAssignmentCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    assignment = await services.create_batch_assignment(db, body.model_dump())
    return schemas.BatchAssignmentResponse.model_validate(assignment)


@router.put("/admin/assignments/{assignment_id}", response_model=schemas.BatchAssignmentResponse)
async def admin_update_batch_assignment(
    assignment_id: int,
    body: schemas.BatchAssignmentUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    assignment = await services.update_batch_assignment(db, assignment_id, body.model_dump(exclude_unset=True))
    return schemas.BatchAssignmentResponse.model_validate(assignment)


@router.delete("/admin/assignments/{assignment_id}", response_model=dict)
async def admin_delete_batch_assignment(
    assignment_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    success = await services.delete_batch_assignment(db, assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch assignment not found")
    return {"message": "Batch assignment deleted successfully"}


@router.get("/admin/assignments/{assignment_id}/submissions", response_model=List[schemas.BatchAssignmentSubmissionResponse])
async def admin_list_batch_assignment_submissions(
    assignment_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    submissions = await services.get_batch_assignment_submissions(db, assignment_id)
    return [schemas.BatchAssignmentSubmissionResponse.model_validate(s) for s in submissions]


@router.post("/admin/assignments/grade", response_model=schemas.BatchAssignmentSubmissionResponse)
async def admin_grade_batch_assignment(
    submission_id: int,
    score: float,
    feedback: str,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    submission = await services.grade_batch_assignment_submission(db, submission_id, score, feedback)
    return schemas.BatchAssignmentSubmissionResponse.model_validate(submission)


@router.get("/admin/list", response_model=schemas.BatchListResponse)
async def admin_list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all active batches (admin only)."""
    batches, total = await services.list_batches(db, skip=skip, limit=limit)
    return schemas.BatchListResponse(
        batches=[schemas.BatchResponse.model_validate(b) for b in batches],
        total=total
    )


@router.post("/admin/create", response_model=schemas.BatchResponse, status_code=201)
async def admin_create_batch(
    body: schemas.BatchCreate,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new batch (either start fresh or duplicate/copy from another batch)."""
    batch = await services.create_batch(db, body.model_dump(), admin.id)
    batch = await services.get_batch_by_id(db, batch.id)
    return schemas.BatchResponse.model_validate(batch)


@router.put("/admin/{id}", response_model=schemas.BatchResponse)
async def admin_update_batch(
    id: int,
    body: schemas.BatchUpdate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Edit batch properties."""
    batch = await services.update_batch(db, id, body.model_dump(exclude_unset=True))
    batch = await services.get_batch_by_id(db, batch.id)
    return schemas.BatchResponse.model_validate(batch)


@router.delete("/admin/{id}", response_model=dict)
async def admin_delete_batch(
    id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a batch."""
    success = await services.delete_batch(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}


@router.post("/admin/{id}/assign-courses", response_model=dict)
async def admin_assign_courses(
    id: int,
    body: schemas.BatchCourseAssign,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Assign/link courses to a batch, auto copying modules and lessons."""
    success = await services.assign_courses_to_batch(db, id, body.course_ids)
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Courses assigned and content copied successfully"}


@router.post("/admin/{id}/courses", response_model=dict, status_code=201)
async def admin_create_batch_only_course(
    id: int,
    body: schemas.BatchOnlyCourseCreate,
    admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a course shell that belongs only to this batch and is hidden from the global Courses tab."""
    course = await services.create_batch_only_course(db, id, body.model_dump(), admin.id)
    return {
        "id": course.id,
        "title": course.title,
        "difficulty_level": course.difficulty_level,
        "duration_hours": course.duration_hours,
        "is_batch_only": True,
    }


@router.get("/admin/{id}/students", response_model=List[schemas.StudentResponse])
async def admin_get_students(
    id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all students enrolled in a batch."""
    students = await services.get_batch_students(db, id)
    return [schemas.StudentResponse(**s) for s in students]


# ── Admin Batch Modules & Lessons Endpoints ─────────────────────────

@router.get("/admin/{id}/courses/{course_id}/structure", response_model=List[schemas.BatchModuleResponse])
async def admin_get_batch_course_structure(
    id: int,
    course_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get the cohort-specific module and lesson structure for a given course in a batch."""
    modules = await services.list_batch_modules(db, id, course_id)
    return [schemas.BatchModuleResponse.model_validate(m) for m in modules]


@router.post("/admin/modules", response_model=schemas.BatchModuleResponse, status_code=201)
async def admin_create_batch_module(
    body: schemas.BatchModuleCreate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cohort-specific batch module."""
    module = await services.create_batch_module(db, body.model_dump())
    await db.refresh(module, ["lessons"])
    return schemas.BatchModuleResponse.model_validate(module)



@router.put("/admin/modules/{module_id}", response_model=schemas.BatchModuleResponse)
async def admin_update_batch_module(
    module_id: int,
    body: schemas.BatchModuleUpdate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a cohort-specific batch module."""
    module = await services.update_batch_module(db, module_id, body.model_dump(exclude_unset=True))
    await db.refresh(module, ["lessons"])
    return schemas.BatchModuleResponse.model_validate(module)


@router.delete("/admin/modules/{module_id}", response_model=dict)
async def admin_delete_batch_module(
    module_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cohort-specific batch module."""
    success = await services.delete_batch_module(db, module_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch module not found")
    return {"message": "Batch module deleted successfully"}


@router.post("/admin/lessons", response_model=schemas.BatchLessonResponse, status_code=201)
async def admin_create_batch_lesson(
    body: schemas.BatchLessonCreate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cohort-specific batch lesson."""
    lesson = await services.create_batch_lesson(db, body.model_dump())
    return schemas.BatchLessonResponse.model_validate(lesson)


@router.put("/admin/lessons/{lesson_id}", response_model=schemas.BatchLessonResponse)
async def admin_update_batch_lesson(
    lesson_id: int,
    body: schemas.BatchLessonUpdate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a cohort-specific batch lesson."""
    lesson = await services.update_batch_lesson(db, lesson_id, body.model_dump(exclude_unset=True))
    return schemas.BatchLessonResponse.model_validate(lesson)


@router.delete("/admin/lessons/{lesson_id}", response_model=dict)
async def admin_delete_batch_lesson(
    lesson_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cohort-specific batch lesson."""
    success = await services.delete_batch_lesson(db, lesson_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch lesson not found")
    return {"message": "Batch lesson deleted successfully"}

# ── Batch Day Tasks ──────────────────────────────────────────────────────────

@router.get("/admin/{batch_id}/courses/{course_id}/day-tasks", response_model=List[schemas.BatchDayTaskResponse])
async def list_day_tasks(
    batch_id: int,
    course_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.modules.batches.models import BatchDayTask

    result = await db.execute(
        select(BatchDayTask)
        .where(BatchDayTask.batch_id == batch_id, BatchDayTask.course_id == course_id)
        .order_by(BatchDayTask.day_number)
    )
    return result.scalars().all()


@router.post("/admin/{batch_id}/courses/{course_id}/day-tasks", response_model=schemas.BatchDayTaskResponse)
async def create_day_task(
    batch_id: int,
    course_id: int,
    payload: schemas.BatchDayTaskCreate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.batches.models import BatchDayTask

    task = BatchDayTask(
        batch_id=batch_id,
        course_id=course_id,
        day_number=payload.day_number,
        title=payload.title,
        content_type=payload.content_type,
        content=payload.content,
        duration_minutes=payload.duration_minutes,
        is_published=payload.is_published,
        start_time=payload.start_time,
        end_time=payload.end_time,
        instructor_name=payload.instructor_name,
        exam_title=payload.exam_title,
        exam_passing_score=payload.exam_passing_score,
        linked_assignment_id=payload.linked_assignment_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/admin/day-tasks/{task_id}", response_model=schemas.BatchDayTaskResponse)
async def update_day_task(
    task_id: int,
    payload: schemas.BatchDayTaskUpdate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.batches.models import BatchDayTask
    from fastapi import HTTPException

    task = await db.get(BatchDayTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(task, k, v)

    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/admin/day-tasks/{task_id}")
async def delete_day_task(
    task_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.batches.models import BatchDayTask
    from fastapi import HTTPException

    task = await db.get(BatchDayTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return {"status": "ok", "message": "Day task deleted successfully"}
