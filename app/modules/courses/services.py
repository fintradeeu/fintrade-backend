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
        query = query.where(Course.is_batch_only == False)
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
        is_featured=data.get("is_featured", False),
        is_popular=data.get("is_popular", False),
        marketing_highlights=data.get("marketing_highlights"),
        is_batch_only=data.get("is_batch_only", False),
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


async def delete_courses(db: AsyncSession, course_ids: List[int]) -> None:
    """Delete multiple courses and all their related content."""
    result = await db.execute(select(Course).where(Course.id.in_(course_ids)))
    courses = result.scalars().all()
    for course in courses:
        await db.delete(course)
    await db.flush()
    logger.info("courses_deleted", course_ids=course_ids)

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
    result = await db.execute(
        select(CourseModule)
        .options(selectinload(CourseModule.lessons))
        .where(CourseModule.id == module_id)
    )
    module = result.scalar_one_or_none()
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
    paid_amount: Optional[float] = None,
) -> CourseEnrollment:
    """Enroll a student in a course, optionally with a distributor referral code."""
    # Verify course exists and is published
    course = await db.get(Course, course_id)
    if course is None or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found or not available")

    # Check if already enrolled
    existing_res = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
        )
    )
    enrollment = existing_res.scalar_one_or_none()
    
    if enrollment:
        if paid_amount is not None:
            enrollment.price_paid = (enrollment.price_paid or 0) + paid_amount
            await db.flush()
            return enrollment
        else:
            raise HTTPException(status_code=409, detail="Already enrolled in this course")

    # Entrance Exam Prerequisite Check (Removed from flow)
    # from app.modules.exams.models import EntranceExam, ExamResult
    # entrance_res = await db.execute(
    #     select(EntranceExam).where(
    #         EntranceExam.course_id == course_id,
    #         EntranceExam.is_active == True
    #     )
    # )
    # exams = entrance_res.scalars().all()
    # if exams:
    #     exam_ids = [e.id for e in exams]
    #     # Check if user has passed any of these entrance exams
    #     passed_res = await db.execute(
    #         select(ExamResult).where(
    #             ExamResult.user_id == user_id,
    #             ExamResult.exam_id.in_(exam_ids),
    #             ExamResult.passed == True
    #         )
    #     )
    #     if not passed_res.scalars().first():
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="You must pass the entrance exam before enrolling in this course."
    #         )

    # Distributor referral logic
    discount_amount = 0.0
    original_price = course.price or 0.0
    price_paid = original_price
    distributor_id = None

    # Split codes if combined
    offer_code = None
    actual_distributor_code = None
    if distributor_code:
        if ":" in distributor_code:
            parts = distributor_code.split(":", 1)
            offer_code = parts[0].strip() or None
            actual_distributor_code = parts[1].strip() or None
        else:
            from app.modules.offers.models import Offer
            offer_result = await db.execute(select(Offer).where(Offer.code == distributor_code))
            if offer_result.scalar_one_or_none():
                offer_code = distributor_code
            else:
                actual_distributor_code = distributor_code

    # Apply offer coupon discount if present
    offer = None
    if offer_code:
        from app.modules.offers.models import Offer
        offer_result = await db.execute(select(Offer).where(Offer.code == offer_code))
        offer = offer_result.scalar_one_or_none()
        if offer and offer.is_active:
            if offer.discount_type == "percentage":
                discount_amount += original_price * (offer.discount_value / 100)
            else:
                discount_amount += offer.discount_value

    # Process distributor referral code if present
    if actual_distributor_code:
        from app.modules.distributors.models import Distributor, StudentReferral
        dist_result = await db.execute(
            select(Distributor).where(Distributor.referral_code == actual_distributor_code)
        )
        distributor = dist_result.scalar_one_or_none()
        if distributor:
            distributor_id = distributor.id
            if distributor.discount_percentage and distributor.discount_percentage > 0:
                discount_amount += original_price * (distributor.discount_percentage / 100)

            # Create referral record
            dup_ref = await db.execute(
                select(StudentReferral).where(
                    StudentReferral.student_id == user_id,
                    StudentReferral.distributor_id == distributor.id,
                    StudentReferral.course_id == course_id
                )
            )
            if not dup_ref.scalar_one_or_none():
                referral = StudentReferral(
                    student_id=user_id,
                    distributor_id=distributor.id,
                    course_id=course_id,
                )
                db.add(referral)
    else:
        # Fallback to existing student referral (if registered via a referral link)
        from app.modules.distributors.models import Distributor, StudentReferral
        # Look up any existing referral for this student
        existing_referral_res = await db.execute(
            select(StudentReferral).where(StudentReferral.student_id == user_id)
        )
        existing_referral = existing_referral_res.scalars().first()

        if existing_referral:
            dist_result = await db.execute(
                select(Distributor).where(Distributor.id == existing_referral.distributor_id)
            )
            distributor = dist_result.scalar_one_or_none()
            if distributor:
                distributor_id = distributor.id
                if distributor.discount_percentage and distributor.discount_percentage > 0:
                    discount_amount += original_price * (distributor.discount_percentage / 100)

                if existing_referral.course_id is None:
                    # Update existing pending referral with the course ID
                    existing_referral.course_id = course_id
                else:
                    # Create a new referral record for this course
                    dup_ref = await db.execute(
                        select(StudentReferral).where(
                            StudentReferral.student_id == user_id,
                            StudentReferral.distributor_id == distributor.id,
                            StudentReferral.course_id == course_id
                        )
                    )
                    if not dup_ref.scalar_one_or_none():
                        referral = StudentReferral(
                            student_id=user_id,
                            distributor_id=distributor.id,
                            course_id=course_id,
                        )
                        db.add(referral)

    if paid_amount is not None:
        price_paid = paid_amount
    else:
        price_paid = max(original_price - discount_amount, 0.0)

    # Save offer redemption if offer was valid and active
    if offer and offer.is_active:
        from app.modules.offers.models import OfferRedemption
        # Check if this user has already redeemed this offer (idempotency check)
        redeemed_res = await db.execute(
            select(OfferRedemption).where(
                OfferRedemption.offer_id == offer.id,
                OfferRedemption.user_id == user_id,
            )
        )
        if not redeemed_res.scalar_one_or_none():
            redemption = OfferRedemption(
                offer_id=offer.id,
                user_id=user_id,
                original_price=original_price,
                discounted_price=price_paid,
            )
            db.add(redemption)
            offer.current_redemptions = (offer.current_redemptions or 0) + 1

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
    try:
        from app.modules.commissions.services import credit_commission_for_enrollment
        await credit_commission_for_enrollment(db, enrollment)
    except Exception as e:
        logger.error("commission_credit_failed", enrollment_id=enrollment.id, error=str(e))
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
    enrollments = list(result.scalars().all())
    if enrollments:
        from app.modules.offers.models import OfferRedemption
        from app.modules.payments.models import PaymentTransaction

        transactions_result = await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(PaymentTransaction.updated_at.desc())
        )
        latest_transactions = {}
        for transaction in transactions_result.scalars().all():
            key = (transaction.user_id, transaction.course_id)
            if key not in latest_transactions or transaction.status == "success":
                latest_transactions[key] = transaction

        redemptions_result = await db.execute(
            select(OfferRedemption)
            .options(selectinload(OfferRedemption.offer))
            .where(OfferRedemption.user_id == user_id)
            .order_by(OfferRedemption.redeemed_at.desc())
        )
        redemptions = list(redemptions_result.scalars().all())

        for enrollment in enrollments:
            transaction = latest_transactions.get((user_id, enrollment.course_id))
            if transaction:
                setattr(enrollment, "payment_amount", transaction.amount)
                setattr(enrollment, "payment_txnid", transaction.txnid)
                if transaction.coupon_code:
                    setattr(enrollment, "coupon_code", transaction.coupon_code)

            for redemption in redemptions:
                offer = redemption.offer
                if offer and offer.course_id and offer.course_id != enrollment.course_id:
                    continue
                price_paid = enrollment.price_paid or 0.0
                original_price = enrollment.course.price if enrollment.course else 0.0
                same_paid_price = abs((redemption.discounted_price or 0.0) - price_paid) <= 0.01
                same_original_price = abs((redemption.original_price or 0.0) - original_price) <= 0.01
                if same_paid_price and same_original_price and offer:
                    if not getattr(enrollment, "coupon_code", None):
                        setattr(enrollment, "coupon_code", offer.code)
                    setattr(enrollment, "coupon_title", offer.title)
                    break

    return enrollments

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
