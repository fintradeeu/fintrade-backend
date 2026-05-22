"""Admin module — aggregated admin API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.admin import schemas, services
from app.modules.auth.models import User
from app.modules.auth.schemas import UserResponse

# Course / Exam / Lecture / Offer schemas for creation
from app.modules.courses import schemas as course_schemas, services as course_services
from app.modules.exams import schemas as exam_schemas, services as exam_services
from app.modules.lectures import schemas as lecture_schemas, services as lecture_services
from app.modules.offers import schemas as offer_schemas, services as offer_services

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Dashboard ────────────────────────────────────────────────────────
@router.get("/stats", response_model=schemas.AdminStatsResponse)
async def admin_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get admin dashboard statistics."""
    stats = await services.get_admin_stats(db)
    return schemas.AdminStatsResponse(**stats)


@router.get("/users", response_model=schemas.UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    data = await services.list_users(db, skip=skip, limit=limit)
    return schemas.UserListResponse(
        users=[UserResponse.model_validate(u) for u in data["users"]],
        total=data["total"],
    )


# ── User management ─────────────────────────────────────────────────
@router.post("/users/create-admin", response_model=UserResponse, status_code=201)
async def create_admin(
    body: schemas.CreateUserRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new admin account (admin only)."""
    user = await services.create_user_with_role(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role_name="admin",
        created_by=admin.id,
        phone=body.phone,
    )
    return UserResponse.model_validate(user)


@router.post("/users/create-faculty", response_model=UserResponse, status_code=201)
async def create_faculty(
    body: schemas.CreateUserRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new faculty account (admin only)."""
    user = await services.create_user_with_role(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role_name="faculty",
        created_by=admin.id,
        phone=body.phone,
    )
    return UserResponse.model_validate(user)


@router.post("/users/create-distributor", response_model=UserResponse, status_code=201)
async def create_distributor(
    body: schemas.CreateDistributorRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new distributor account with profile (admin only)."""
    user, distributor = await services.create_distributor_user(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        region=body.region,
        referral_code=body.referral_code,
        discount_percentage=body.discount_percentage,
        created_by=admin.id,
        phone=body.phone,
    )
    return UserResponse.model_validate(user)


# ── Distributor management ──────────────────────────────────────────
@router.get("/distributors", response_model=List[schemas.AdminDistributorResponse])
async def list_distributors(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all distributors (admin only)."""
    distributors = await services.list_distributors(db)
    return [
        schemas.AdminDistributorResponse(
            id=d.id,
            user_id=d.user_id,
            region=d.region,
            referral_code=d.referral_code,
            discount_percentage=d.discount_percentage,
            created_at=d.created_at,
            user_name=d.user.full_name if d.user else None,
            user_email=d.user.email if d.user else None,
        )
        for d in distributors
    ]


@router.get("/distributors/{distributor_id}/stats", response_model=schemas.AdminDistributorStatsResponse)
async def distributor_stats(
    distributor_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get stats for a specific distributor (admin only)."""
    stats = await services.get_distributor_stats(db, distributor_id)
    return schemas.AdminDistributorStatsResponse(**stats)


# ── Course management ────────────────────────────────────────────────
@router.get("/courses", response_model=List[course_schemas.CourseListResponse])
async def admin_list_courses(
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
):
    """List all courses including drafts (admin/faculty only)."""
    courses = await course_services.list_courses(db, skip=skip, limit=limit, published_only=False)
    return [course_schemas.CourseListResponse.model_validate(c) for c in courses]

@router.post("/courses", response_model=course_schemas.CourseDetailResponse, status_code=201)
async def create_course(
    body: course_schemas.CourseCreate,
    admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new course (admin/faculty only)."""
    data = body.model_dump()
    # Default to published if not explicitly set
    if data.get("is_published") is None:
        data["is_published"] = True
    course = await course_services.create_course(db, data, created_by=admin.id)
    return course_schemas.CourseDetailResponse.model_validate(course)


@router.post("/courses/publish-all")
async def publish_all_courses(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Publish all draft courses (admin only)."""
    from sqlalchemy import update
    from app.modules.courses.models import Course
    result = await db.execute(
        update(Course).where(Course.is_published == False).values(is_published=True)  # noqa: E712
    )
    await db.flush()
    return {"published_count": result.rowcount, "message": f"{result.rowcount} courses published."}


@router.put("/courses/{course_id}", response_model=course_schemas.CourseDetailResponse)
async def update_course(
    course_id: int,
    body: course_schemas.CourseUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a course (admin only)."""
    course = await course_services.update_course(db, course_id, body.model_dump(exclude_unset=True))
    return course_schemas.CourseDetailResponse.model_validate(course)


@router.delete("/courses/{course_id}", response_model=schemas.MessageResponse)
async def delete_course(
    course_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a course (admin only)."""
    await course_services.delete_course(db, course_id)
    return schemas.MessageResponse(message="Course deleted successfully")


@router.post("/modules", response_model=course_schemas.ModuleResponse, status_code=201)
async def create_module(
    body: course_schemas.ModuleCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a course module (admin/faculty only)."""
    module = await course_services.create_module(db, body.model_dump())
    return course_schemas.ModuleResponse.model_validate(module)


@router.put("/modules/{module_id}", response_model=course_schemas.ModuleResponse)
async def update_module(
    module_id: int,
    body: course_schemas.ModuleUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a course module (admin/faculty only)."""
    module = await course_services.update_module(db, module_id, body.model_dump(exclude_unset=True))
    return course_schemas.ModuleResponse.model_validate(module)


@router.post("/lessons", response_model=course_schemas.LessonResponse, status_code=201)
async def create_lesson(
    body: course_schemas.LessonCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a lesson in a module (admin/faculty only)."""
    lesson = await course_services.create_lesson(db, body.model_dump())
    return course_schemas.LessonResponse.model_validate(lesson)


@router.put("/lessons/{lesson_id}", response_model=course_schemas.LessonResponse)
async def update_lesson(
    lesson_id: int,
    body: course_schemas.LessonUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a lesson (admin/faculty only)."""
    lesson = await course_services.update_lesson(db, lesson_id, body.model_dump(exclude_unset=True))
    return course_schemas.LessonResponse.model_validate(lesson)


@router.delete("/modules/{module_id}", response_model=schemas.MessageResponse)
async def delete_module(
    module_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a module and all its lessons (admin/faculty only)."""
    await course_services.delete_module(db, module_id)
    return schemas.MessageResponse(message="Module deleted successfully")


@router.put("/courses/{course_id}/modules/reorder", response_model=schemas.MessageResponse)
async def reorder_modules(
    course_id: int,
    body: course_schemas.ModuleReorder,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Reorder modules within a course."""
    await course_services.reorder_modules(db, course_id, body.module_ids)
    return schemas.MessageResponse(message="Modules reordered successfully")


@router.delete("/lessons/{lesson_id}", response_model=schemas.MessageResponse)
async def delete_lesson(
    lesson_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a lesson (admin/faculty only)."""
    await course_services.delete_lesson(db, lesson_id)
    return schemas.MessageResponse(message="Lesson deleted successfully")


@router.post("/assignments", response_model=course_schemas.AssignmentResponse, status_code=201)
async def create_assignment(
    body: course_schemas.AssignmentCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new assignment for a course (admin/faculty only)."""
    assignment = await course_services.create_assignment(db, body.model_dump())
    return course_schemas.AssignmentResponse.model_validate(assignment)

@router.get("/assignments/{assignment_id}/submissions", response_model=List[course_schemas.AssignmentSubmissionResponse])
async def list_assignment_submissions(
    assignment_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all submissions for a specific assignment (admin/faculty only)."""
    submissions = await course_services.get_assignment_submissions(db, assignment_id)
    return [course_schemas.AssignmentSubmissionResponse.model_validate(s) for s in submissions]

@router.post("/assignments/grade", response_model=course_schemas.AssignmentSubmissionResponse)
async def grade_assignment(
    submission_id: int,
    score: float,
    feedback: str,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Grade an assignment submission (admin/faculty only)."""
    submission = await course_services.grade_assignment_submission(db, submission_id, score, feedback)
    return course_schemas.AssignmentSubmissionResponse.model_validate(submission)


# ── Exam management ─────────────────────────────────────────────────
@router.post("/exams/create", response_model=exam_schemas.EntranceExamResponse, status_code=201)
async def create_exam(
    body: exam_schemas.EntranceExamCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create an entrance exam with questions (admin only)."""
    exam = await exam_services.create_exam(db, body.model_dump())
    return exam_schemas.EntranceExamResponse.model_validate(exam)

@router.post("/exams/course-create", response_model=exam_schemas.CourseExamResponse, status_code=201)
async def create_course_exam(
    body: exam_schemas.CourseExamCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a course or module exam with questions (admin only)."""
    exam = await exam_services.create_course_exam(db, body.model_dump())
    return exam_schemas.CourseExamResponse.model_validate(exam)

@router.put("/exams/{exam_id}", response_model=exam_schemas.EntranceExamResponse)
async def update_entrance_exam(
    exam_id: int,
    body: exam_schemas.ExamUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update entrance exam metadata."""
    exam = await exam_services.update_exam(db, exam_id, body.model_dump(exclude_unset=True), is_course_exam=False)
    return exam_schemas.EntranceExamResponse.model_validate(exam)

@router.put("/course-exams/{exam_id}", response_model=exam_schemas.CourseExamResponse)
async def update_course_exam(
    exam_id: int,
    body: exam_schemas.ExamUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update course exam metadata."""
    exam = await exam_services.update_exam(db, exam_id, body.model_dump(exclude_unset=True), is_course_exam=True)
    return exam_schemas.CourseExamResponse.model_validate(exam)

@router.get("/exams/all", response_model=dict)
async def list_all_exams(
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all exams (both entrance and course exams) with question counts for admin."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.exams.models import EntranceExam, CourseExam
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Entrance Exams
        req1 = await db.execute(
            select(EntranceExam)
            .options(selectinload(EntranceExam.questions))
            .order_by(EntranceExam.created_at.desc())
        )
        entrance_exams = req1.scalars().all()
        
        # Course Exams
        req2 = await db.execute(
            select(CourseExam)
            .options(selectinload(CourseExam.questions))
            .order_by(CourseExam.created_at.desc())
        )
        course_exams = req2.scalars().all()

        return {
            "entrance_exams": [
                {
                    "id": e.id, "title": e.title, "duration_minutes": e.duration_minutes, 
                    "passing_score": e.passing_score, "is_active": e.is_active, 
                    "questions_count": len(e.questions), "type": "entrance"
                } for e in entrance_exams
            ],
            "course_exams": [
                {
                    "id": e.id, "title": e.title, "duration_minutes": e.duration_minutes, 
                    "passing_score": e.passing_score, "is_active": e.is_active, 
                    "questions_count": len(e.questions), "type": e.exam_type,
                    "course_id": e.course_id, "module_id": e.module_id
                } for e in course_exams
            ]
        }
    except Exception as e:
        logger.error(f"Error in list_all_exams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exams/questions-list")
async def get_exam_questions(
    exam_id: int = Query(..., description="Exam to fetch questions for"),
    is_course: bool = Query(False, description="True for course exams, False for entrance exams"),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all questions for a given exam (admin/faculty only)."""
    questions = await exam_services.get_admin_exam_questions(db, exam_id, is_course)
    result = []
    for q in questions:
        result.append({
            "id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "marks": q.marks,
            "negative_marks": q.negative_marks,
            "category": q.category or "",
            "explanation": q.explanation or "",
            "options": [
                {"id": o.id, "option_text": o.option_text, "is_correct": o.is_correct}
                for o in (q.options or [])
            ]
        })
    return result


@router.put("/exams/questions/{question_id}")
async def update_question(
    question_id: int,
    body: dict,
    is_course: bool = Query(False),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a single question and its options (admin/faculty only)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError
    from app.modules.exams.models import ExamQuestion, CourseExamQuestion, ExamOption, CourseExamOption
    
    QuestionModel = CourseExamQuestion if is_course else ExamQuestion
    OptionModel = CourseExamOption if is_course else ExamOption
    
    result = await db.execute(
        select(QuestionModel).options(selectinload(QuestionModel.options)).where(QuestionModel.id == question_id)
    )
    question = result.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Update question fields
    for field in ["question_text", "question_type", "marks", "negative_marks", "category", "explanation"]:
        if field in body:
            setattr(question, field, body[field])
    
    # Update options if provided
    if "options" in body:
        existing_options = {opt.id: opt for opt in question.options}
        
        for i, opt_data in enumerate(body["options"]):
            if "id" in opt_data and opt_data["id"] in existing_options:
                opt = existing_options[opt_data["id"]]
                opt.option_text = opt_data["option_text"]
                opt.is_correct = opt_data.get("is_correct", False)
                opt.order = i
                del existing_options[opt.id]
            else:
                new_opt = OptionModel(
                    question_id=question.id,
                    option_text=opt_data["option_text"],
                    is_correct=opt_data.get("is_correct", False),
                    order=i,
                )
                db.add(new_opt)
                
        # Remove remaining options
        for opt in existing_options.values():
            try:
                await db.delete(opt)
                await db.flush()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=400, detail=f"Cannot delete option '{opt.option_text}' because it has already been selected in student exam attempts.")
    
    await db.commit()
    await db.refresh(question)
    return {"message": "Question updated successfully"}


@router.delete("/exams/questions/{question_id}")
async def delete_question(
    question_id: int,
    is_course: bool = Query(False),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single question and its options (admin/faculty only)."""
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.modules.exams.models import ExamQuestion, CourseExamQuestion
    
    QuestionModel = CourseExamQuestion if is_course else ExamQuestion
    result = await db.execute(select(QuestionModel).where(QuestionModel.id == question_id))
    question = result.scalars().first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    await db.delete(question)  # cascade deletes options
    await db.flush()
    return {"message": "Question deleted successfully"}


@router.post("/exams/questions", response_model=schemas.MessageResponse, status_code=201)
async def add_questions(
    exam_id: int = Query(..., description="Exam to add questions to"),
    body: List[exam_schemas.ExamQuestionCreate] = ...,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Add questions to an existing entrance exam (admin/faculty only)."""
    await exam_services.add_questions_to_exam(db, exam_id, [q.model_dump() for q in body], is_course_exam=False)
    return schemas.MessageResponse(message=f"Added {len(body)} questions to exam {exam_id}")


@router.post("/course-exams/questions", response_model=schemas.MessageResponse, status_code=201)
async def add_course_questions(
    exam_id: int = Query(..., description="Exam to add questions to"),
    body: List[exam_schemas.ExamQuestionCreate] = ...,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Add questions to an existing course exam (admin/faculty only)."""
    await exam_services.add_questions_to_exam(db, exam_id, [q.model_dump() for q in body], is_course_exam=True)
    return schemas.MessageResponse(message=f"Added {len(body)} questions to exam {exam_id}")


@router.post("/exams/upload-questions", response_model=schemas.MessageResponse, status_code=201)
async def upload_exam_questions(
    exam_id: int = Query(..., description="Exam to add questions to"),
    is_course_exam: bool = Query(False, description="True for course exams, False for entrance exams"),
    file: UploadFile = File(...),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Bulk upload questions from CSV or Excel file (admin/faculty only).

    Expected columns: question, option_a, option_b, option_c, option_d, correct_answer
    Optional columns: marks, negative_marks, category, explanation, question_type
    """
    contents = await file.read()
    questions = await exam_services.parse_questions_from_file(contents, file.filename or "upload.csv")
    await exam_services.add_questions_to_exam(db, exam_id, questions, is_course_exam=is_course_exam)
    return schemas.MessageResponse(message=f"Parsed and added {len(questions)} questions from '{file.filename}' to exam {exam_id}")


@router.post("/exams/preview-upload")
async def preview_upload(
    file: UploadFile = File(...),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
):
    """Preview parsed questions from a CSV/Excel file without saving them.

    Returns the parsed question list so the teacher can review before confirming.
    """
    contents = await file.read()
    questions = await exam_services.parse_questions_from_file(contents, file.filename or "upload.csv")
    return {"count": len(questions), "questions": questions}


# ── Offer management ────────────────────────────────────────────────
@router.post("/offers", response_model=offer_schemas.OfferResponse, status_code=201)
async def create_offer(
    body: offer_schemas.OfferCreate,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new offer (admin only)."""
    data = body.model_dump()
    data["created_by_admin"] = admin.id
    offer = await offer_services.create_offer(db, data)
    return offer_schemas.OfferResponse.model_validate(offer)


@router.get("/offers", response_model=List[offer_schemas.OfferResponse])
async def list_all_offers(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all offers including inactive ones (admin only)."""
    offers = await offer_services.list_offers(db, active_only=False)
    return [offer_schemas.OfferResponse.model_validate(o) for o in offers]


@router.put("/offers/{offer_id}", response_model=offer_schemas.OfferResponse)
async def update_offer(
    offer_id: int,
    body: offer_schemas.OfferCreate,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing offer/coupon (admin only)."""
    offer = await offer_services.update_offer(db, offer_id, body.model_dump(exclude_unset=True))
    return offer_schemas.OfferResponse.model_validate(offer)


@router.delete("/offers/{offer_id}", response_model=schemas.MessageResponse)
async def delete_offer(
    offer_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete an offer/coupon (admin only)."""
    await offer_services.delete_offer(db, offer_id)
    return schemas.MessageResponse(message="Offer deleted successfully")


@router.put("/offers/{offer_id}/toggle", response_model=offer_schemas.OfferResponse)
async def toggle_offer(
    offer_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Toggle offer active/inactive status (admin only)."""
    offer = await offer_services.toggle_offer(db, offer_id)
    return offer_schemas.OfferResponse.model_validate(offer)


@router.get("/offers/stats", response_model=dict)
async def offer_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get coupon/offer usage statistics (admin only)."""
    return await offer_services.get_offer_stats(db)


@router.get("/revenue/stats", response_model=dict)
async def revenue_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue statistics (hardcoded for now, Finance/Super Admin only)."""
    return {
        "total_revenue": "₹2.45Cr",
        "monthly_revenue": "₹24.5L",
        "active_coupons": (await offer_services.get_offer_stats(db))["active_coupons"],
        "total_usage": (await offer_services.get_offer_stats(db))["total_usage"],
    }


# ── Lecture management ──────────────────────────────────────────────
@router.post("/lectures", response_model=lecture_schemas.LectureResponse, status_code=201)
async def create_lecture(
    body: lecture_schemas.LectureCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a new lecture (admin/faculty only)."""
    import traceback
    try:
        lecture = await lecture_services.create_lecture(db, body.model_dump())
        return lecture_schemas.LectureResponse.model_validate(lecture)
    except Exception as e:
        from fastapi import HTTPException
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@router.put("/lectures/{lecture_id}", response_model=lecture_schemas.LectureResponse)
async def update_lecture(
    lecture_id: int,
    body: lecture_schemas.LectureUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled lecture (admin/faculty only)."""
    lecture = await lecture_services.update_lecture(db, lecture_id, body.model_dump(exclude_unset=True))
    return lecture_schemas.LectureResponse.model_validate(lecture)

@router.delete("/lectures/{lecture_id}", status_code=204)
async def delete_lecture(
    lecture_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled lecture (admin/faculty only)."""
    await lecture_services.delete_lecture(db, lecture_id)

@router.put("/lectures/{lecture_id}/start", response_model=lecture_schemas.LectureResponse)
async def start_lecture(
    lecture_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Start a lecture (admin/faculty only)."""
    lecture = await lecture_services.start_lecture(db, lecture_id)
    return lecture_schemas.LectureResponse.model_validate(lecture)

@router.put("/lectures/{lecture_id}/end", response_model=lecture_schemas.LectureResponse)
async def end_lecture(
    lecture_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """End a lecture (admin/faculty only)."""
    lecture = await lecture_services.end_lecture(db, lecture_id)
    return lecture_schemas.LectureResponse.model_validate(lecture)

@router.post("/lectures/{lecture_id}/recordings", response_model=lecture_schemas.RecordingResponse, status_code=201)
async def add_lecture_recording(
    lecture_id: int,
    body: lecture_schemas.RecordingCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Add a recording to a completed lecture (admin/faculty only)."""
    recording = await lecture_services.add_recording(db, lecture_id, body.recording_url)
    return lecture_schemas.RecordingResponse.model_validate(recording)

# ── Media Upload ────────────────────────────────────────────────────
import os
import uuid
from fastapi import UploadFile, File, HTTPException
from app.modules.admin.schemas import MessageResponse

@router.post("/upload", response_model=dict, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    _admin: User = Depends(require_roles(["admin", "faculty"])),
):
    """Upload media file (video/audio) for courses/lessons."""
    try:
        os.makedirs("uploads", exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join("uploads", unique_name)
        
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)
            
        return {"url": f"/uploads/{unique_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not upload file: {str(e)}")


# ── Phase 3: Advanced Dashboard Reports ─────────────────────────────

@router.get("/reports", response_model=schemas.AdminReportsResponse)
async def admin_reports(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated student analytics report."""
    data = await services.get_admin_reports(db)
    return schemas.AdminReportsResponse(**data)


@router.get("/certificates", response_model=schemas.AdminCertificatesResponse)
async def admin_certificates(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get certificate stats and recent certificates."""
    data = await services.get_admin_certificates(db)
    return schemas.AdminCertificatesResponse(**data)


@router.get("/simulator", response_model=schemas.AdminSimulatorResponse)
async def admin_simulator(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get simulator usage stats and top performers."""
    data = await services.get_admin_simulator(db)
    return schemas.AdminSimulatorResponse(**data)



# --- AI FAQ Management ---

from app.modules.ai.models import FAQEntry
from app.modules.ai import schemas as ai_schemas
from sqlalchemy import select

@router.get('/ai/faqs', response_model=list[ai_schemas.FAQResponse])
async def get_faqs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FAQEntry).order_by(FAQEntry.frequency.desc()))
    return result.scalars().all()

@router.post('/ai/faqs', response_model=ai_schemas.FAQResponse)
async def create_faq(body: ai_schemas.FAQCreate, db: AsyncSession = Depends(get_db)):
    faq = FAQEntry(**body.model_dump())
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq

@router.put('/ai/faqs/{faq_id}', response_model=ai_schemas.FAQResponse)
async def update_faq(faq_id: int, body: ai_schemas.FAQUpdate, db: AsyncSession = Depends(get_db)):
    faq = await db.get(FAQEntry, faq_id)
    if not faq:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail='FAQ not found')
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(faq, k, v)
    await db.commit()
    await db.refresh(faq)
    return faq

@router.delete('/ai/faqs/{faq_id}')
async def delete_faq(faq_id: int, db: AsyncSession = Depends(get_db)):
    faq = await db.get(FAQEntry, faq_id)
    if faq:
        await db.delete(faq)
        await db.commit()
    return {'status': 'ok'}

# --- Simulator Admin ---
@router.post('/simulator/toggle')
async def toggle_simulator(status: bool, db: AsyncSession = Depends(get_db)):
    # Basic toggle placeholder
    return {'status': 'ok', 'simulator_active': status}
