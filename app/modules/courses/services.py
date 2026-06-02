"""Courses module — service layer."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import selectinload

from app.modules.courses.models import Course, CourseEnrollment, CourseModule, Lesson
from app.utils.helpers import slugify
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Courses ──────────────────────────────────────────────────────────
async def list_courses(
    db: AsyncSession, skip: int = 0, limit: int = 20, published_only: bool = True,
    is_featured: Optional[bool] = None
) -> List[Course]:
    """Return paginated list of courses."""
    query = select(Course).offset(skip).limit(limit).order_by(Course.created_at.desc())
    if published_only:
        query = query.where(Course.is_published == True)  # noqa: E712
    if is_featured is not None:
        query = query.where(Course.is_featured == is_featured)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_course(db: AsyncSession, course_id: int) -> Course:
    """Get a single course with its modules and lessons."""
    result = await db.execute(
        select(Course)
        .options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .where(Course.id == course_id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


async def create_course(db: AsyncSession, data: dict, created_by: int) -> Course:
    """Admin creates a new course."""
    slug = slugify(data["title"])
    # Check slug uniqueness
    existing = await db.execute(select(Course).where(Course.slug == slug))
    if existing.scalar_one_or_none():
        # Append a suffix
        import time
        slug = f"{slug}-{int(time.time()) % 10000}"

    course = Course(
        title=data["title"],
        slug=slug,
        description=data.get("description"),
        short_description=data.get("short_description"),
        thumbnail_url=data.get("thumbnail_url"),
        price=data.get("price", 0.0),
        original_price=data.get("original_price"),
        difficulty_level=data.get("difficulty_level", "beginner"),
        duration_hours=data.get("duration_hours"),
        is_published=data.get("is_published", False),
        created_by=data.get("instructor_id") or created_by,
    )
    db.add(course)
    await db.flush()
    await db.refresh(course)
    
    set_committed_value(course, 'modules', [])
    set_committed_value(course, 'enrollments', [])
    
    logger.info("course_created", course_id=course.id, title=course.title)
    return course


async def update_course(db: AsyncSession, course_id: int, data: dict) -> Course:
    """Update an existing course."""
    result = await db.execute(
        select(Course)
        .options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .where(Course.id == course_id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    for key, value in data.items():
        if value is not None and hasattr(course, key):
            setattr(course, key, value)

    await db.flush()
    await db.refresh(course)
    logger.info("course_updated", course_id=course.id, title=course.title)
    return course

async def delete_course(db: AsyncSession, course_id: int) -> None:
    """Delete a course and all its related content."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    await db.delete(course)
    await db.flush()
    logger.info("course_deleted", course_id=course_id)

# ── Modules ──────────────────────────────────────────────────────────
async def create_module(db: AsyncSession, data: dict) -> CourseModule:
    """Admin creates a module for a course."""
    # Verify course exists
    course = await db.get(Course, data["course_id"])
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    module = CourseModule(
        course_id=data["course_id"],
        title=data["title"],
        description=data.get("description"),
        order=data.get("order", 0),
        is_published=data.get("is_published", False),
    )
    db.add(module)
    await db.flush()
    await db.refresh(module)
    set_committed_value(module, 'lessons', [])
    logger.info("module_created", module_id=module.id, course_id=module.course_id)
    return module


async def update_module(db: AsyncSession, module_id: int, data: dict) -> CourseModule:
    """Update an existing module."""
    module = await db.get(CourseModule, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")

    for key, value in data.items():
        if value is not None and hasattr(module, key):
            setattr(module, key, value)

    await db.flush()
    await db.refresh(module)
    logger.info("module_updated", module_id=module.id)
    return module

async def reorder_modules(db: AsyncSession, course_id: int, module_ids: List[int]) -> None:
    """Bulk update module orders based on array index."""
    result = await db.execute(select(CourseModule).where(CourseModule.course_id == course_id))
    modules = result.scalars().all()
    
    # Create a map of module_id to order index
    order_map = {mod_id: idx for idx, mod_id in enumerate(module_ids)}
    
    for module in modules:
        if module.id in order_map:
            module.order = order_map[module.id]
            
    await db.flush()


# ── Lessons ──────────────────────────────────────────────────────────
async def create_lesson(db: AsyncSession, data: dict) -> Lesson:
    """Admin creates a lesson for a module."""
    module = await db.get(CourseModule, data["module_id"])
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")

    lesson = Lesson(
        module_id=data["module_id"],
        title=data["title"],
        content=data.get("content"),
        content_type=data.get("content_type", "text"),
        video_url=data.get("video_url"),
        duration_minutes=data.get("duration_minutes"),
        order=data.get("order", 0),
        is_published=data.get("is_published", False),
    )
    db.add(lesson)
    await db.flush()
    await db.refresh(lesson)
    logger.info("lesson_created", lesson_id=lesson.id, module_id=lesson.module_id)
    return lesson


async def update_lesson(db: AsyncSession, lesson_id: int, data: dict) -> Lesson:
    """Update an existing lesson."""
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    for key, value in data.items():
        if value is not None and hasattr(lesson, key):
            setattr(lesson, key, value)

    await db.flush()
    await db.refresh(lesson)
    logger.info("lesson_updated", lesson_id=lesson.id)
    return lesson


async def delete_module(db: AsyncSession, module_id: int) -> None:
    """Delete a module and all its lessons (cascade)."""
    module = await db.get(CourseModule, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    await db.delete(module)
    await db.flush()
    logger.info("module_deleted", module_id=module_id)


async def delete_lesson(db: AsyncSession, lesson_id: int) -> None:
    """Delete a single lesson."""
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    await db.delete(lesson)
    await db.flush()
    logger.info("lesson_deleted", lesson_id=lesson_id)


# ── Enrollment ───────────────────────────────────────────────────────
async def enroll_user(
    db: AsyncSession,
    user_id: int,
    course_id: int,
    distributor_code: Optional[str] = None,
) -> CourseEnrollment:
    """Enroll a student in a course, optionally with a distributor referral code."""
    # Verify course exists and is published
    course = await db.get(Course, course_id)
    if course is None or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found or not available")

    # Check if already enrolled
    existing = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already enrolled in this course")

    # Entrance Exam Prerequisite Check
    from app.modules.exams.models import EntranceExam, ExamResult
    entrance_res = await db.execute(
        select(EntranceExam).where(
            EntranceExam.course_id == course_id,
            EntranceExam.is_active == True
        )
    )
    entrance_exam = entrance_res.scalar_one_or_none()
    if entrance_exam:
        # Check if user has passed this entrance exam
        passed_res = await db.execute(
            select(ExamResult).where(
                ExamResult.user_id == user_id,
                ExamResult.exam_id == entrance_exam.id,
                ExamResult.passed == True
            )
        )
        if not passed_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must pass the entrance exam before enrolling in this course."
            )

    # Distributor referral logic
    discount_amount = 0.0
    original_price = course.price or 0.0
    price_paid = original_price
    distributor_id = None

    if distributor_code:
        from app.modules.distributors.models import Distributor, StudentReferral
        from app.modules.offers.models import Offer

        # Check if it's an offer first
        offer_result = await db.execute(select(Offer).where(Offer.code == distributor_code))
        offer = offer_result.scalar_one_or_none()
        
        if offer:
            if offer.discount_type == "percentage":
                discount_amount = original_price * (offer.discount_value / 100)
            else:
                discount_amount = offer.discount_value
            price_paid = max(original_price - discount_amount, 0.0)
            # Note: /offers/apply already recorded the OfferRedemption
        else:
            dist_result = await db.execute(
                select(Distributor).where(Distributor.referral_code == distributor_code)
            )
            distributor = dist_result.scalar_one_or_none()
            if distributor is None:
                raise HTTPException(status_code=400, detail="Invalid offer or distributor referral code")

            distributor_id = distributor.id
            if distributor.discount_percentage and distributor.discount_percentage > 0:
                discount_amount = original_price * (distributor.discount_percentage / 100)
                price_paid = max(original_price - discount_amount, 0.0)

            # Create referral record
            referral = StudentReferral(
                student_id=user_id,
                distributor_id=distributor.id,
                course_id=course_id,
            )
            db.add(referral)

    enrollment = CourseEnrollment(
        user_id=user_id,
        course_id=course_id,
        discount_applied=round(discount_amount, 2),
        price_paid=round(price_paid, 2),
        distributor_id=distributor_id,
    )
    db.add(enrollment)
    await db.flush()
    await db.refresh(enrollment)
    logger.info(
        "user_enrolled",
        user_id=user_id,
        course_id=course_id,
        distributor_code=distributor_code,
        discount=discount_amount,
    )
    return enrollment


async def get_enrolled_courses(db: AsyncSession, user_id: int) -> List[CourseEnrollment]:
    """Get all courses a user is enrolled in."""
    result = await db.execute(
        select(CourseEnrollment)
        .options(selectinload(CourseEnrollment.course))
        .where(CourseEnrollment.user_id == user_id, CourseEnrollment.is_active == True)  # noqa: E712
        .order_by(CourseEnrollment.enrolled_at.desc())
    )
    return list(result.scalars().all())

# ── Assignments ──────────────────────────────────────────────────────
from app.modules.courses.models import Assignment, AssignmentSubmission

async def create_assignment(db: AsyncSession, data: dict) -> Assignment:
    assignment = Assignment(
        course_id=data["course_id"],
        module_id=data.get("module_id"),
        title=data["title"],
        description=data.get("description"),
        due_date=data.get("due_date"),
        max_score=data.get("max_score", 100.0),
        resources=data.get("resources")
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def get_all_assignments(db: AsyncSession) -> List[Assignment]:
    result = await db.execute(select(Assignment))
    return result.scalars().all()

async def get_course_assignments(db: AsyncSession, course_id: int) -> List[Assignment]:
    result = await db.execute(
        select(Assignment).where(Assignment.course_id == course_id)
    )
    return list(result.scalars().all())

async def get_assignment_submissions(db: AsyncSession, assignment_id: int) -> List[AssignmentSubmission]:
    result = await db.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment_id)
    )
    return list(result.scalars().all())

async def get_user_assignment_submissions(db: AsyncSession, user_id: int) -> List[AssignmentSubmission]:
    result = await db.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.user_id == user_id)
    )
    return list(result.scalars().all())

async def submit_assignment(db: AsyncSession, data: dict, user_id: int) -> AssignmentSubmission:
    submission = AssignmentSubmission(
        assignment_id=data["assignment_id"],
        user_id=user_id,
        file_url=data["file_url"]
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return submission

async def grade_assignment_submission(db: AsyncSession, submission_id: int, score: float, feedback: str) -> AssignmentSubmission:
    submission = await db.get(AssignmentSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    submission.score = score
    submission.teacher_feedback = feedback
    submission.status = "graded"
    await db.flush()
    await db.refresh(submission)
    return submission
