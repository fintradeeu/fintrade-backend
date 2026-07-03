"""Batches module — business logic and services."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.batches.models import (
    Batch,
    BatchCourse,
    BatchModule,
    BatchLesson,
    BatchLecture,
    StudentBatchEnrollment,
    BatchAssignment,
    BatchAssignmentSubmission,
    BatchLessonCompletion,
)
from app.modules.courses.models import Assignment, Course, CourseModule, Lesson, CourseEnrollment
from app.modules.lectures.models import Lecture
from app.modules.auth.models import User


def update_batch_status_based_on_dates(batch: Batch) -> str:
    """Helper to dynamically calculate the batch status based on current UTC time."""
    now = datetime.now(timezone.utc)
    
    # If the status is manually archived, keep it archived
    if batch.status == "Archived":
        return "Archived"
        
    if now < batch.registration_start_date:
        return "Upcoming"
    elif batch.registration_start_date <= now <= batch.registration_end_date:
        return "Registration Open"
    elif batch.registration_end_date < now < batch.start_date:
        return "Registration Closed"
    elif batch.start_date <= now <= batch.end_date:
        return "Running"
    else:
        return "Completed"


async def list_batches(db: AsyncSession, skip: int = 0, limit: int = 50) -> (List[Batch], int):
    # Total count
    count_stmt = select(func.count(Batch.id)).where(Batch.is_active == True)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    stmt = (
        select(Batch)
        .options(selectinload(Batch.courses).selectinload(BatchCourse.course))
        .where(Batch.is_active == True)
        .order_by(Batch.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    res = await db.execute(stmt)
    batches = list(res.scalars().all())

    # Dynamically sync/update status for all listed batches
    for b in batches:
        calculated_status = update_batch_status_based_on_dates(b)
        if b.status != calculated_status:
            b.status = calculated_status
    await db.commit()

    return batches, total


async def get_batch_by_id(db: AsyncSession, batch_id: int) -> Batch:
    stmt = (
        select(Batch)
        .options(selectinload(Batch.courses).selectinload(BatchCourse.course))
        .where(Batch.id == batch_id, Batch.is_active == True)
    )
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    calculated_status = update_batch_status_based_on_dates(batch)
    if batch.status != calculated_status:
        batch.status = calculated_status
        await db.commit()
        await db.refresh(batch)
    return batch


async def create_batch(db: AsyncSession, data: dict, creator_id: int) -> Batch:
    # Generate unique batch code
    batch_code = f"BT-{uuid.uuid4().hex[:8].upper()}"
    copy_from_id = data.pop("copy_from_batch_id", None)

    new_batch = Batch(
        batch_code=batch_code,
        created_by=creator_id,
        **data
    )
    new_batch.status = update_batch_status_based_on_dates(new_batch)
    db.add(new_batch)
    await db.flush()
    await db.refresh(new_batch)

    # If copying from an existing batch
    if copy_from_id:
        await copy_batch_content(db, from_batch_id=copy_from_id, to_batch_id=new_batch.id)

    await db.commit()
    await db.refresh(new_batch)
    return new_batch


async def update_batch(db: AsyncSession, batch_id: int, data: dict) -> Batch:
    batch = await get_batch_by_id(db, batch_id)
    for key, val in data.items():
        if val is not None:
            setattr(batch, key, val)
    batch.status = update_batch_status_based_on_dates(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


async def delete_batch(db: AsyncSession, batch_id: int) -> bool:
    batch = await db.get(Batch, batch_id)
    if not batch:
        return False
    batch.is_active = False
    await db.commit()
    return True


async def copy_batch_content(db: AsyncSession, from_batch_id: int, to_batch_id: int):
    """Deep copy all associated courses, modules, lessons, lectures, and assignments from one batch to another."""
    # 1. Copy Courses
    courses_res = await db.execute(select(BatchCourse).where(BatchCourse.batch_id == from_batch_id))
    courses = courses_res.scalars().all()
    for c in courses:
        db.add(BatchCourse(batch_id=to_batch_id, course_id=c.course_id))

    # 2. Copy Modules & Lessons
    modules_res = await db.execute(
        select(BatchModule).options(selectinload(BatchModule.lessons)).where(BatchModule.batch_id == from_batch_id)
    )
    modules = modules_res.scalars().all()
    for m in modules:
        new_module = BatchModule(
            batch_id=to_batch_id,
            course_id=m.course_id,
            template_module_id=m.template_module_id,
            title=m.title,
            description=m.description,
            order=m.order,
            is_published=m.is_published,
        )
        db.add(new_module)
        await db.flush() # Get new_module.id

        for l in m.lessons:
            new_lesson = BatchLesson(
                batch_module_id=new_module.id,
                template_lesson_id=l.template_lesson_id,
                title=l.title,
                content=l.content,
                content_type=l.content_type,
                video_url=l.video_url,
                duration_minutes=l.duration_minutes,
                order=l.order,
                is_published=l.is_published,
            )
            db.add(new_lesson)

    # 3. Copy Lectures
    lectures_res = await db.execute(select(BatchLecture).where(BatchLecture.batch_id == from_batch_id))
    lectures = lectures_res.scalars().all()
    for lec in lectures:
        new_lec = BatchLecture(
            batch_id=to_batch_id,
            course_id=lec.course_id,
            title=lec.title,
            description=lec.description,
            meeting_link=lec.meeting_link,
            scheduled_at=lec.scheduled_at,
            duration_minutes=lec.duration_minutes,
            is_live=lec.is_live,
            is_completed=lec.is_completed,
        )
        db.add(new_lec)

    # 4. Copy Assignments
    assignments_res = await db.execute(select(BatchAssignment).where(BatchAssignment.batch_id == from_batch_id))
    assignments = assignments_res.scalars().all()
    for a in assignments:
        # Resolve mapped module (if any) by matching the title
        new_module_id = None
        if a.batch_module_id:
            orig_module = await db.get(BatchModule, a.batch_module_id)
            if orig_module:
                new_mod_res = await db.execute(
                    select(BatchModule).where(
                        BatchModule.batch_id == to_batch_id,
                        BatchModule.course_id == a.course_id,
                        BatchModule.title == orig_module.title
                    )
                )
                new_mod = new_mod_res.scalar_one_or_none()
                if new_mod:
                    new_module_id = new_mod.id

        new_a = BatchAssignment(
            batch_id=to_batch_id,
            course_id=a.course_id,
            batch_module_id=new_module_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            max_score=a.max_score,
            resources=a.resources,
        )
        db.add(new_a)


async def assign_courses_to_batch(db: AsyncSession, batch_id: int, course_ids: List[int]) -> bool:
    batch = await get_batch_by_id(db, batch_id)

    existing_res = await db.execute(select(BatchCourse).where(BatchCourse.batch_id == batch_id))
    existing_links = list(existing_res.scalars().all())
    existing_ids = {link.course_id for link in existing_links}
    requested_ids = set(course_ids)

    remove_ids = existing_ids - requested_ids
    add_ids = requested_ids - existing_ids

    for cid in remove_ids:
        await db.execute(delete(BatchAssignment).where(BatchAssignment.batch_id == batch_id, BatchAssignment.course_id == cid))
        await db.execute(delete(BatchLecture).where(BatchLecture.batch_id == batch_id, BatchLecture.course_id == cid))
        await db.execute(delete(BatchModule).where(BatchModule.batch_id == batch_id, BatchModule.course_id == cid))
        await db.execute(delete(BatchCourse).where(BatchCourse.batch_id == batch_id, BatchCourse.course_id == cid))

    for cid in add_ids:
        db.add(BatchCourse(batch_id=batch_id, course_id=cid))

        modules_res = await db.execute(
            select(CourseModule).options(selectinload(CourseModule.lessons)).where(
                CourseModule.course_id == cid
            )
        )
        modules = modules_res.scalars().all()
        for m in modules:
            new_module = BatchModule(
                batch_id=batch_id,
                course_id=cid,
                template_module_id=m.id,
                title=m.title,
                description=m.description,
                order=m.order,
                is_published=m.is_published,
            )
            db.add(new_module)
            await db.flush()

            for l in m.lessons:
                new_lesson = BatchLesson(
                    batch_module_id=new_module.id,
                    template_lesson_id=l.id,
                    title=l.title,
                    content=l.content,
                    content_type=l.content_type,
                    video_url=l.video_url,
                    duration_minutes=l.duration_minutes,
                    order=l.order,
                    is_published=l.is_published,
                )
                db.add(new_lesson)

        lectures_res = await db.execute(select(Lecture).where(Lecture.course_id == cid))
        lectures = lectures_res.scalars().all()
        for lec in lectures:
            db.add(BatchLecture(
                batch_id=batch_id,
                course_id=cid,
                title=lec.title,
                description=lec.description,
                meeting_link=lec.meeting_link,
                scheduled_at=lec.scheduled_at,
                duration_minutes=lec.duration_minutes,
                is_live=lec.is_live,
                is_completed=lec.is_completed,
            ))

        assignments_res = await db.execute(select(Assignment).where(Assignment.course_id == cid))
        assignments = assignments_res.scalars().all()
        for assignment in assignments:
            batch_module_id = None
            if assignment.module_id:
                module_res = await db.execute(
                    select(BatchModule).where(
                        BatchModule.batch_id == batch_id,
                        BatchModule.course_id == cid,
                        BatchModule.template_module_id == assignment.module_id,
                    )
                )
                batch_module = module_res.scalar_one_or_none()
                if batch_module:
                    batch_module_id = batch_module.id

            db.add(BatchAssignment(
                batch_id=batch_id,
                course_id=cid,
                batch_module_id=batch_module_id,
                title=assignment.title,
                description=assignment.description,
                due_date=assignment.due_date,
                max_score=assignment.max_score,
                resources=assignment.resources,
            ))

    await db.commit()
    return True


async def create_batch_only_course(db: AsyncSession, batch_id: int, data: dict, creator_id: int) -> Course:
    await get_batch_by_id(db, batch_id)

    from app.modules.courses.services import create_course

    course_data = {
        "title": data["title"],
        "description": data.get("description"),
        "short_description": data.get("short_description"),
        "difficulty_level": data.get("difficulty_level") or "beginner",
        "duration_hours": data.get("duration_hours"),
        "price": 0.0,
        "original_price": None,
        "is_published": False,
        "is_featured": False,
        "is_popular": False,
        "is_batch_only": True,
    }
    course = await create_course(db, course_data, created_by=creator_id)
    db.add(BatchCourse(batch_id=batch_id, course_id=course.id))
    await db.commit()
    await db.refresh(course)
    return course


async def get_batch_students(db: AsyncSession, batch_id: int) -> List[dict]:
    stmt = select(StudentBatchEnrollment, User).join(
        User, StudentBatchEnrollment.user_id == User.id
    ).where(StudentBatchEnrollment.batch_id == batch_id, StudentBatchEnrollment.is_active == True)
    res = await db.execute(stmt)
    rows = res.all()
    
    students = []
    for enr, user in rows:
        students.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "enrolled_at": enr.enrolled_at,
        })
    return students


async def get_student_current_batch(db: AsyncSession, user_id: int) -> Optional[Batch]:
    stmt = select(Batch).join(
        StudentBatchEnrollment, StudentBatchEnrollment.batch_id == Batch.id
    ).where(
        StudentBatchEnrollment.user_id == user_id,
        StudentBatchEnrollment.is_active == True,
        Batch.is_active == True
    ).order_by(StudentBatchEnrollment.enrolled_at.desc()).limit(1)
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()
    if batch:
        calculated_status = update_batch_status_based_on_dates(batch)
        if batch.status != calculated_status:
            batch.status = calculated_status
            await db.commit()
            await db.refresh(batch)
    return batch


async def get_student_batch_dashboard(db: AsyncSession, user_id: int) -> dict:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        raise HTTPException(status_code=404, detail="You are not enrolled in any batch currently.")

    now = datetime.now(timezone.utc)
    is_locked = now < batch.start_date
    countdown_seconds = int(max(0, (batch.start_date - now).total_seconds()))

    # Load assigned courses from batch-specific tables
    courses_res = await db.execute(
        select(Course).join(BatchCourse, BatchCourse.course_id == Course.id).where(BatchCourse.batch_id == batch.id)
    )
    courses = courses_res.scalars().all()

    assigned_courses = []
    for c in courses:
        # Load progress from course_enrollment of student
        progress_stmt = select(CourseEnrollment.progress_percent).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == c.id
        )
        progress_res = await db.execute(progress_stmt)
        progress = progress_res.scalar() or 0.0

        assigned_courses.append({
            "course_id": c.id,
            "title": c.title,
            "thumbnail_url": c.thumbnail_url,
            "progress_percent": progress,
        })

    avg_progress = 0.0
    if assigned_courses:
        avg_progress = round(sum(c["progress_percent"] for c in assigned_courses) / len(assigned_courses), 2)

    return {
        "batch_id": batch.id,
        "name": batch.name,
        "batch_code": batch.batch_code,
        "status": batch.status,
        "start_date": batch.start_date,
        "end_date": batch.end_date,
        "countdown_seconds": countdown_seconds,
        "is_locked": is_locked,
        "assigned_courses": assigned_courses,
        "progress_percent": avg_progress,
    }


async def enroll_student_in_batch(
    db: AsyncSession,
    user_id: int,
    batch_id: int,
    price_paid: float = 0.0,
    discount_applied: float = 0.0
) -> StudentBatchEnrollment:
    # Deduplicate checking
    dup_stmt = select(StudentBatchEnrollment).where(
        StudentBatchEnrollment.user_id == user_id,
        StudentBatchEnrollment.batch_id == batch_id
    )
    dup_res = await db.execute(dup_stmt)
    existing = dup_res.scalar_one_or_none()
    if existing:
        return existing

    enrollment = StudentBatchEnrollment(
        user_id=user_id,
        batch_id=batch_id,
        price_paid=price_paid,
        discount_applied=discount_applied
    )
    db.add(enrollment)

    # Increment batch student count
    batch = await db.get(Batch, batch_id)
    if batch:
        batch.current_students += 1

    await db.flush()
    return enrollment


async def auto_enroll_student_in_active_batch(db: AsyncSession, user_id: int, course_id: int, price_paid: float = 0.0) -> Optional[StudentBatchEnrollment]:
    try:
        now = datetime.now(timezone.utc)
        batch_stmt = (
            select(Batch)
            .join(BatchCourse, BatchCourse.batch_id == Batch.id)
            .where(
                BatchCourse.course_id == course_id,
                Batch.is_active == True,
                Batch.registration_start_date <= now,
                Batch.registration_end_date >= now
            )
            .order_by(Batch.start_date.asc())
            .limit(1)
        )
        batch_res = await db.execute(batch_stmt)
        batch = batch_res.scalar_one_or_none()
        if batch:
            enrollment = await enroll_student_in_batch(
                db,
                user_id=user_id,
                batch_id=batch.id,
                price_paid=price_paid,
                discount_applied=0.0
            )
            return enrollment
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to auto-enroll user {user_id} in active batch for course {course_id}: {e}")
    return None


async def enroll_student_in_batch_or_active(
    db: AsyncSession,
    user_id: int,
    course_id: int,
    batch_id: Optional[int] = None,
    price_paid: float = 0.0
) -> Optional[StudentBatchEnrollment]:
    try:
        if batch_id:
            return await enroll_student_in_batch(db, user_id=user_id, batch_id=batch_id, price_paid=price_paid)
        else:
            return await auto_enroll_student_in_active_batch(db, user_id=user_id, course_id=course_id, price_paid=price_paid)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"enroll_student_in_batch_or_active failed: {e}")
    return None


# ── Batch Modules & Lessons Admin Services ─────────────────────────

async def list_batch_modules(db: AsyncSession, batch_id: int, course_id: int) -> List[BatchModule]:
    stmt = (
        select(BatchModule)
        .options(selectinload(BatchModule.lessons))
        .where(BatchModule.batch_id == batch_id, BatchModule.course_id == course_id)
        .order_by(BatchModule.order.asc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def list_student_batch_modules(db: AsyncSession, user_id: int, course_id: int) -> List[BatchModule]:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        raise HTTPException(status_code=404, detail="No active batch enrollment found.")

    assigned_stmt = select(BatchCourse).where(
        BatchCourse.batch_id == batch.id,
        BatchCourse.course_id == course_id,
    )
    assigned_res = await db.execute(assigned_stmt)
    if not assigned_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course is not assigned to your batch.")

    return await list_batch_modules(db, batch.id, course_id)

async def create_batch_module(db: AsyncSession, data: dict) -> BatchModule:
    module = BatchModule(**data)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module

async def update_batch_module(db: AsyncSession, module_id: int, data: dict) -> BatchModule:
    module = await db.get(BatchModule, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Batch module not found")
    for key, value in data.items():
        if value is not None:
            setattr(module, key, value)
    await db.commit()
    await db.refresh(module)
    return module

async def delete_batch_module(db: AsyncSession, module_id: int) -> bool:
    module = await db.get(BatchModule, module_id)
    if not module:
        return False
    lesson_ids_res = await db.execute(
        select(BatchLesson.id).where(BatchLesson.batch_module_id == module_id)
    )
    lesson_ids = list(lesson_ids_res.scalars().all())
    if lesson_ids:
        await db.execute(
            delete(BatchLessonCompletion).where(BatchLessonCompletion.batch_lesson_id.in_(lesson_ids))
        )
    await db.delete(module)
    await db.commit()
    return True

async def create_batch_lesson(db: AsyncSession, data: dict) -> BatchLesson:
    lesson = BatchLesson(**data)
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson

async def update_batch_lesson(db: AsyncSession, lesson_id: int, data: dict) -> BatchLesson:
    lesson = await db.get(BatchLesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Batch lesson not found")
    for key, value in data.items():
        if value is not None:
            setattr(lesson, key, value)
    await db.commit()
    await db.refresh(lesson)
    return lesson

async def delete_batch_lesson(db: AsyncSession, lesson_id: int) -> bool:
    lesson = await db.get(BatchLesson, lesson_id)
    if not lesson:
        return False
    await db.execute(
        delete(BatchLessonCompletion).where(BatchLessonCompletion.batch_lesson_id == lesson_id)
    )
    await db.delete(lesson)
    await db.commit()
    return True


async def mark_batch_lesson_completed(db: AsyncSession, user_id: int, course_id: int, batch_lesson_id: int) -> bool:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        raise HTTPException(status_code=404, detail="No active batch enrollment found.")

    lesson_stmt = (
        select(BatchLesson, BatchModule)
        .join(BatchModule, BatchLesson.batch_module_id == BatchModule.id)
        .where(
            BatchLesson.id == batch_lesson_id,
            BatchModule.batch_id == batch.id,
            BatchModule.course_id == course_id,
        )
    )
    lesson_res = await db.execute(lesson_stmt)
    row = lesson_res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Batch lesson not found")

    existing_stmt = select(BatchLessonCompletion).where(
        BatchLessonCompletion.user_id == user_id,
        BatchLessonCompletion.batch_lesson_id == batch_lesson_id,
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        return True

    db.add(BatchLessonCompletion(
        user_id=user_id,
        batch_lesson_id=batch_lesson_id,
        batch_id=batch.id,
        course_id=course_id,
    ))

    enrollment_res = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.is_active == True,
        )
    )
    enrollment = enrollment_res.scalar_one_or_none()
    if enrollment:
        total_res = await db.execute(
            select(func.count(BatchLesson.id))
            .join(BatchModule, BatchLesson.batch_module_id == BatchModule.id)
            .where(
                BatchModule.batch_id == batch.id,
                BatchModule.course_id == course_id,
                BatchLesson.is_published == True,
            )
        )
        total_lessons = total_res.scalar() or 1

        completed_res = await db.execute(
            select(func.count(BatchLessonCompletion.id)).where(
                BatchLessonCompletion.user_id == user_id,
                BatchLessonCompletion.batch_id == batch.id,
                BatchLessonCompletion.course_id == course_id,
            )
        )
        completed_count = completed_res.scalar() or 0
        enrollment.progress_percent = round((completed_count / total_lessons) * 100, 2)
        if enrollment.progress_percent >= 100.0:
            enrollment.progress_percent = 100.0
            if not enrollment.completed_at:
                enrollment.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return True


# ── Batch Lectures ───────────────────────────────────────────────────

async def list_batch_lectures(db: AsyncSession, batch_id: Optional[int] = None, course_id: Optional[int] = None) -> List[BatchLecture]:
    stmt = select(BatchLecture).order_by(BatchLecture.scheduled_at.desc())
    if batch_id:
        stmt = stmt.where(BatchLecture.batch_id == batch_id)
    if course_id:
        stmt = stmt.where(BatchLecture.course_id == course_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def list_student_batch_lectures(db: AsyncSession, user_id: int) -> List[BatchLecture]:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        return []
    return await list_batch_lectures(db, batch_id=batch.id)


async def create_batch_lecture(db: AsyncSession, data: dict) -> BatchLecture:
    await get_batch_by_id(db, data["batch_id"])
    lecture = BatchLecture(**data)
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture


async def update_batch_lecture(db: AsyncSession, lecture_id: int, data: dict) -> BatchLecture:
    lecture = await db.get(BatchLecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Batch lecture not found")
    for key, value in data.items():
        if value is not None and hasattr(lecture, key):
            setattr(lecture, key, value)
    await db.commit()
    await db.refresh(lecture)
    return lecture


async def delete_batch_lecture(db: AsyncSession, lecture_id: int) -> bool:
    lecture = await db.get(BatchLecture, lecture_id)
    if not lecture:
        return False
    await db.delete(lecture)
    await db.commit()
    return True


# ── Batch Assignments ────────────────────────────────────────────────

async def list_batch_assignments(db: AsyncSession, batch_id: Optional[int] = None, course_id: Optional[int] = None) -> List[BatchAssignment]:
    stmt = select(BatchAssignment).order_by(BatchAssignment.created_at.desc())
    if batch_id:
        stmt = stmt.where(BatchAssignment.batch_id == batch_id)
    if course_id:
        stmt = stmt.where(BatchAssignment.course_id == course_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def list_student_batch_assignments(db: AsyncSession, user_id: int) -> List[BatchAssignment]:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        return []
    return await list_batch_assignments(db, batch_id=batch.id)


async def create_batch_assignment(db: AsyncSession, data: dict) -> BatchAssignment:
    await get_batch_by_id(db, data["batch_id"])
    assignment = BatchAssignment(**data)
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def update_batch_assignment(db: AsyncSession, assignment_id: int, data: dict) -> BatchAssignment:
    assignment = await db.get(BatchAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Batch assignment not found")
    for key, value in data.items():
        if value is not None and hasattr(assignment, key):
            setattr(assignment, key, value)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def delete_batch_assignment(db: AsyncSession, assignment_id: int) -> bool:
    assignment = await db.get(BatchAssignment, assignment_id)
    if not assignment:
        return False
    await db.delete(assignment)
    await db.commit()
    return True


async def get_batch_assignment_submissions(db: AsyncSession, assignment_id: int) -> List[BatchAssignmentSubmission]:
    res = await db.execute(
        select(BatchAssignmentSubmission).where(BatchAssignmentSubmission.batch_assignment_id == assignment_id)
    )
    return list(res.scalars().all())


async def get_user_batch_assignment_submissions(db: AsyncSession, user_id: int) -> List[BatchAssignmentSubmission]:
    res = await db.execute(
        select(BatchAssignmentSubmission).where(BatchAssignmentSubmission.user_id == user_id)
    )
    return list(res.scalars().all())


async def submit_batch_assignment(db: AsyncSession, user_id: int, assignment_id: int, file_url: str) -> BatchAssignmentSubmission:
    batch = await get_student_current_batch(db, user_id)
    if not batch:
        raise HTTPException(status_code=404, detail="No active batch enrollment found.")
    assignment = await db.get(BatchAssignment, assignment_id)
    if not assignment or assignment.batch_id != batch.id:
        raise HTTPException(status_code=404, detail="Batch assignment not found")

    submission = BatchAssignmentSubmission(
        batch_assignment_id=assignment_id,
        user_id=user_id,
        file_url=file_url,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def grade_batch_assignment_submission(db: AsyncSession, submission_id: int, score: float, feedback: str) -> BatchAssignmentSubmission:
    submission = await db.get(BatchAssignmentSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Batch assignment submission not found")
    submission.score = score
    submission.teacher_feedback = feedback
    submission.status = "graded"
    await db.commit()
    await db.refresh(submission)
    return submission


# ── Forward Propagation / Sync from template course modifications ──────

async def propagate_module_creation(db: AsyncSession, template_module):
    """When a new module is added to a template course, auto-propagate to all linked batches."""
    from app.modules.batches.models import BatchCourse, BatchModule
    # Find batches linked to this course
    stmt = select(BatchCourse).where(BatchCourse.course_id == template_module.course_id)
    res = await db.execute(stmt)
    links = res.scalars().all()
    for link in links:
        bm = BatchModule(
            batch_id=link.batch_id,
            course_id=template_module.course_id,
            template_module_id=template_module.id,
            title=template_module.title,
            description=template_module.description,
            order=template_module.order,
            is_published=template_module.is_published,
        )
        db.add(bm)
    await db.commit()


async def propagate_module_update(db: AsyncSession, template_module_id: int, update_data: dict):
    """Propagate changes to a template module to all corresponding batch modules."""
    from app.modules.batches.models import BatchModule
    stmt = select(BatchModule).where(BatchModule.template_module_id == template_module_id)
    res = await db.execute(stmt)
    bmods = res.scalars().all()
    for bm in bmods:
        for key, val in update_data.items():
            if val is not None:
                setattr(bm, key, val)
    await db.commit()


async def propagate_lesson_creation(db: AsyncSession, template_lesson):
    """When a new lesson is added to a template course module, auto-propagate to all corresponding batch modules."""
    from app.modules.courses.models import CourseModule
    from app.modules.batches.models import BatchCourse, BatchModule, BatchLesson
    # Get parent module
    cm = await db.get(CourseModule, template_lesson.module_id)
    if not cm:
        return
    # Find batches linked to this course
    stmt = select(BatchCourse).where(BatchCourse.course_id == cm.course_id)
    res = await db.execute(stmt)
    links = res.scalars().all()
    for link in links:
        # Find corresponding BatchModule
        stmt_bm = select(BatchModule).where(
            BatchModule.batch_id == link.batch_id,
            BatchModule.template_module_id == cm.id
        )
        res_bm = await db.execute(stmt_bm)
        bm = res_bm.scalar_one_or_none()
        if bm:
            bl = BatchLesson(
                batch_module_id=bm.id,
                template_lesson_id=template_lesson.id,
                title=template_lesson.title,
                content=template_lesson.content,
                content_type=template_lesson.content_type,
                video_url=template_lesson.video_url,
                duration_minutes=template_lesson.duration_minutes,
                order=template_lesson.order,
                is_published=template_lesson.is_published,
            )
            db.add(bl)
    await db.commit()


async def propagate_lesson_update(db: AsyncSession, template_lesson_id: int, update_data: dict):
    """Propagate changes to a template lesson (e.g. video upload URL) to all corresponding batch lessons."""
    from app.modules.batches.models import BatchLesson
    stmt = select(BatchLesson).where(BatchLesson.template_lesson_id == template_lesson_id)
    res = await db.execute(stmt)
    blessons = res.scalars().all()
    for bl in blessons:
        for key, val in update_data.items():
            if val is not None:
                setattr(bl, key, val)
    await db.commit()
