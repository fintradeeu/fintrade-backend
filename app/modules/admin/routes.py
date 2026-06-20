"""Admin module — aggregated admin API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles, get_current_user
from app.db.database import get_db
from app.modules.admin import schemas, services
from app.modules.auth.models import User
from app.modules.auth.schemas import UserResponse
from app.modules.distributors.schemas import ReferralResponse

# Course / Exam / Lecture / Offer schemas for creation
from app.modules.courses import schemas as course_schemas, services as course_services
from app.modules.exams import schemas as exam_schemas, services as exam_services
from app.modules.lectures import schemas as lecture_schemas, services as lecture_services
from app.modules.offers import schemas as offer_schemas, services as offer_services

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_super_admin_user(user: User) -> None:
    if not any(role.name == "super_admin" for role in user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Super Admin role")


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
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    data = await services.list_users(db, skip=skip, limit=limit)
    users = data["users"]
    users = [
        user
        for user in users
        if not any(role.name == "distributor" for role in user.roles)
    ]
    return schemas.UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=len(users) if users != data["users"] else data["total"],
    )


# ── User management ─────────────────────────────────────────────────
@router.post("/users/create-admin", response_model=UserResponse, status_code=201)
async def create_admin(
    body: schemas.CreateUserRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new admin account (admin only)."""
    user_role_names = {r.name for r in admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin has access to create Admin users"
        )
    user = await services.create_user_with_role(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role_name="admin",
        created_by=admin.id,
        phone=body.phone,
        city=body.city,
        bank_account_holder_name=body.bank_account_holder_name,
        bank_name=body.bank_name,
        bank_account_number=body.bank_account_number,
        bank_ifsc_code=body.bank_ifsc_code,
        bank_upi_id=body.bank_upi_id,
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
        city=body.city,
        permissions=body.permissions,
    )
    return UserResponse.model_validate(user)


@router.post("/users/create-distributor", response_model=UserResponse, status_code=201)
async def create_distributor(
    body: schemas.CreateDistributorRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new distributor/IB account (Super Admin only)."""
    user_role_names = {r.name for r in admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can create Introducing Broker (IB) accounts"
        )
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
        city=body.city,
    )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: schemas.UpdateUserRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update user details (admin only)."""
    user = await services.update_user(db, user_id, body.model_dump(exclude_unset=True))
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", response_model=schemas.MessageResponse)
async def delete_user(
    user_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (admin only)."""
    await services.delete_user(db, user_id)
    return schemas.MessageResponse(message="User deleted successfully")


# ── Distributor management ──────────────────────────────────────────
@router.get("/distributors", response_model=List[schemas.AdminDistributorResponse])
async def list_distributors(
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all distributors (Super Admin only)."""
    require_super_admin_user(admin)
    from sqlalchemy import select, func
    from app.modules.distributors.models import StudentReferral
    from app.modules.courses.models import CourseEnrollment

    distributors = await services.list_distributors(db)
    
    # Query count of referred students grouped by distributor_id
    counts_res = await db.execute(
        select(StudentReferral.distributor_id, func.count(func.distinct(StudentReferral.student_id)))
        .group_by(StudentReferral.distributor_id)
    )
    counts_map = {row[0]: row[1] for row in counts_res.all()}

    # Query total revenue generated grouped by distributor_id
    revenue_res = await db.execute(
        select(CourseEnrollment.distributor_id, func.coalesce(func.sum(CourseEnrollment.price_paid), 0.0))
        .where(CourseEnrollment.distributor_id.isnot(None))
        .group_by(CourseEnrollment.distributor_id)
    )
    revenue_map = {row[0]: float(row[1]) for row in revenue_res.all()}

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
            phone=d.user.phone if d.user else None,
            city=d.user.city if d.user else None,
            profile_photo_url=d.profile_photo_url,
            aadhaar_card_url=d.aadhaar_card_url,
            pan_card_url=d.pan_card_url,
            bank_account_holder_name=d.bank_account_holder_name,
            bank_name=d.bank_name,
            bank_account_number=d.bank_account_number,
            bank_ifsc_code=d.bank_ifsc_code,
            bank_upi_id=d.bank_upi_id,
            self_registered=d.self_registered,
            verification_status=d.verification_status,
            total_students_referred=counts_map.get(d.id, 0),
            total_revenue_generated=revenue_map.get(d.id, 0.0),
        )
        for d in distributors
    ]


@router.get("/distributors/{distributor_id}/stats", response_model=schemas.AdminDistributorStatsResponse)
async def distributor_stats(
    distributor_id: int,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get stats for a specific distributor (Super Admin only)."""
    require_super_admin_user(admin)
    stats = await services.get_distributor_stats(db, distributor_id)
    return schemas.AdminDistributorStatsResponse(**stats)


@router.get("/distributors/{distributor_id}/referrals", response_model=List[ReferralResponse])
async def list_distributor_referrals(
    distributor_id: int,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List referred students for a specific distributor (Super Admin only)."""
    require_super_admin_user(admin)
    from app.modules.distributors import services as dist_services
    
    referrals = await dist_services.list_referrals(db, distributor_id)
    return [
        ReferralResponse(
            id=r.id,
            student_id=r.student_id,
            student_name=r.student.full_name if r.student else None,
            student_email=r.student.email if r.student else None,
            course_id=r.course_id,
            course_title=r.course.title if r.course else None,
            created_at=r.created_at,
        )
        for r in referrals
    ]


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
    _admin: User = Depends(require_roles(["admin"])),
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



@router.get("/assignments", response_model=List[course_schemas.AssignmentResponse])
async def list_all_assignments(
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all assignments across all courses (admin/faculty only)."""
    assignments = await course_services.get_all_assignments(db)
    return [course_schemas.AssignmentResponse.model_validate(a) for a in assignments]

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

@router.delete("/exams/{exam_id}", response_model=schemas.MessageResponse)
async def delete_entrance_exam(
    exam_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.exams.models import EntranceExam
    exam = await db.get(EntranceExam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await db.delete(exam)
    await db.commit()
    return schemas.MessageResponse(message="Exam deleted successfully")

@router.delete("/course-exams/{exam_id}", response_model=schemas.MessageResponse)
async def delete_course_exam(
    exam_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.exams.models import CourseExam
    exam = await db.get(CourseExam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await db.delete(exam)
    await db.commit()
    return schemas.MessageResponse(message="Exam deleted successfully")

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
    user_role_names = {r.name for r in admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
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
    user_role_names = {r.name for r in _admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
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
    user_role_names = {r.name for r in _admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
    offer = await offer_services.update_offer(db, offer_id, body.model_dump(exclude_unset=True))
    return offer_schemas.OfferResponse.model_validate(offer)


@router.delete("/offers/{offer_id}", response_model=schemas.MessageResponse)
async def delete_offer(
    offer_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete an offer/coupon (admin only)."""
    user_role_names = {r.name for r in _admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
    await offer_services.delete_offer(db, offer_id)
    return schemas.MessageResponse(message="Offer deleted successfully")


@router.put("/offers/{offer_id}/toggle", response_model=offer_schemas.OfferResponse)
async def toggle_offer(
    offer_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Toggle offer active/inactive status (admin only)."""
    user_role_names = {r.name for r in _admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
    offer = await offer_services.toggle_offer(db, offer_id)
    return offer_schemas.OfferResponse.model_validate(offer)


@router.get("/offers/stats", response_model=dict)
async def offer_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get coupon/offer usage statistics (admin only)."""
    user_role_names = {r.name for r in _admin.roles}
    if "super_admin" not in user_role_names:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Requires Super Admin role"
        )
    return await offer_services.get_offer_stats(db)


@router.get("/revenue/stats", response_model=dict)
async def revenue_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue statistics (Super Admin only)."""
    from fastapi import HTTPException
    
    user_role_names = {r.name for r in current_user.roles}
    if "super_admin" not in user_role_names:
        raise HTTPException(status_code=403, detail="Requires Super Admin role")

    # Calculate actual revenue from database
    from app.modules.payments.models import PaymentTransaction
    from sqlalchemy import func, select
    
    total_stmt = select(func.sum(PaymentTransaction.amount)).where(PaymentTransaction.status == "success")
    total_val = (await db.execute(total_stmt)).scalar() or 0.0

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    monthly_stmt = select(func.sum(PaymentTransaction.amount)).where(
        PaymentTransaction.status == "success",
        PaymentTransaction.updated_at >= start_of_month
    )
    monthly_val = (await db.execute(monthly_stmt)).scalar() or 0.0

    return {
        "total_revenue": f"₹{total_val:,.2f}",
        "monthly_revenue": f"₹{monthly_val:,.2f}",
        "active_coupons": (await offer_services.get_offer_stats(db))["active_coupons"],
        "total_usage": (await offer_services.get_offer_stats(db))["total_usage"],
    }


@router.get("/revenue/details")
async def revenue_details(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed transaction history (Super Admin only)."""
    from fastapi import HTTPException
    
    user_role_names = {r.name for r in current_user.roles}
    if "super_admin" not in user_role_names:
        raise HTTPException(status_code=403, detail="Requires Super Admin role")

    from app.modules.payments.models import PaymentTransaction
    from app.modules.courses.models import Course
    from sqlalchemy import select
    
    # Query database for transactions joined with user and course
    stmt = (
        select(PaymentTransaction, User.full_name, User.email, Course.title)
        .join(User, User.id == PaymentTransaction.user_id)
        .join(Course, Course.id == PaymentTransaction.course_id)
        .where(PaymentTransaction.status == "success")
        .order_by(PaymentTransaction.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        {
            "id": tx.id,
            "txnid": tx.txnid,
            "amount": tx.amount,
            "status": tx.status,
            "payment_mode": tx.payment_mode or "N/A",
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
            "student_name": full_name,
            "student_email": email,
            "course_title": title,
        }
        for tx, full_name, email, title in rows
    ]



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

@router.get("/lectures/registrations", response_model=List[lecture_schemas.LectureRegistrationResponse])
async def list_lecture_registrations(
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all live class registrations (admin/faculty only)."""
    registrations = await lecture_services.get_all_lecture_registrations(db)
    return [lecture_schemas.LectureRegistrationResponse.model_validate(r) for r in registrations]

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


# In-memory mock for Admin Roles
mock_admins = [
    {
      "id": 1,
      "name": "Rajesh Mehta",
      "email": "rajesh.mehta@fintrade.in",
      "role": "Super Admin",
      "status": "Active",
      "permissions": {
        "manageCourses": True,
        "manageStudents": True,
        "managePayments": True,
        "manageContent": True,
        "manageExams": True,
        "manageAdmins": True,
        "canViewRevenue": True,
      },
      "lastActive": "2026-04-16"
    }
]

@router.get("/roles")
async def get_admin_roles(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.auth.models import Role

    # Fetch all users that have the 'admin' role
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .join(User.roles)
        .where(Role.name == "admin")
    )
    admins = result.scalars().all()

    res = []
    for a in admins:
        perms = a.permissions if isinstance(a.permissions, dict) else {}
        role_name = perms.get("roleName", "Super Admin" if a.email == "admin@platform.com" else "Admin")
        is_default_super = a.email == "admin@platform.com"
        
        permissions_dict = {
            "manageCourses": perms.get("manageCourses", True if is_default_super else False),
            "manageStudents": perms.get("manageStudents", True if is_default_super else False),
            "managePayments": perms.get("managePayments", True if is_default_super else False),
            "manageContent": perms.get("manageContent", True if is_default_super else False),
            "directPublish": perms.get("directPublish", True if is_default_super else False),
            "manageExams": perms.get("manageExams", True if is_default_super else False),
            "manageAdmins": perms.get("manageAdmins", True if is_default_super else False),
            "canViewRevenue": perms.get("canViewRevenue", True if is_default_super else False),
            "viewDashboard": perms.get("viewDashboard", True),
            "viewModuleStudents": perms.get("viewModuleStudents", True),
            "viewLectures": perms.get("viewLectures", True),
            "viewLoginDetails": perms.get("viewLoginDetails", True),
            "viewSiteContent": perms.get("viewSiteContent", True),
            "viewAIChatbot": perms.get("viewAIChatbot", True),
            "viewSimulator": perms.get("viewSimulator", True),
            "viewContracts": perms.get("viewContracts", True),
            "viewSettings": perms.get("viewSettings", True),
        }
        
        res.append({
            "id": a.id,
            "name": a.full_name,
            "email": a.email,
            "phone": a.phone,
            "role": role_name,
            "status": "Active" if a.is_active else "Inactive",
            "permissions": permissions_dict,
            "lastActive": a.updated_at.isoformat() if a.updated_at else a.created_at.isoformat()
        })
    return res


@router.post("/roles")
async def create_admin_role(
    data: dict, 
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.modules.auth.services import get_or_create_role

    email = data.get("email").strip().lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")

    admin_role = await get_or_create_role(db, "admin")
    password = data.get("password") or "admin123!"

    perms = data.get("permissions", {})
    user_perms = {
        "roleName": data.get("role"),
        "manageCourses": perms.get("manageCourses", False),
        "manageStudents": perms.get("manageStudents", False),
        "managePayments": perms.get("managePayments", False),
        "manageContent": perms.get("manageContent", False),
        "directPublish": perms.get("directPublish", False),
        "manageExams": perms.get("manageExams", False),
        "manageAdmins": perms.get("manageAdmins", False),
        "canViewRevenue": perms.get("canViewRevenue", False),
        "viewDashboard": perms.get("viewDashboard", True),
        "viewModuleStudents": perms.get("viewModuleStudents", False),
        "viewLectures": perms.get("viewLectures", False),
        "viewLoginDetails": perms.get("viewLoginDetails", False),
        "viewSiteContent": perms.get("viewSiteContent", False),
        "viewAIChatbot": perms.get("viewAIChatbot", False),
        "viewSimulator": perms.get("viewSimulator", False),
        "viewContracts": perms.get("viewContracts", False),
        "viewSettings": perms.get("viewSettings", False),
    }

    new_user = User(
        email=email,
        full_name=data.get("name"),
        phone=data.get("phone"),
        hashed_password=hash_password(password),
        is_active=True if data.get("status") == "Active" else False,
        is_verified=True,
        permissions=user_perms
    )
    new_user.roles.append(admin_role)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {
        "id": new_user.id,
        "name": new_user.full_name,
        "email": new_user.email,
        "phone": new_user.phone,
        "role": data.get("role"),
        "status": data.get("status"),
        "permissions": perms,
        "lastActive": new_user.created_at.isoformat()
    }


@router.put("/roles/{role_id}")
async def update_admin_role(
    role_id: int, 
    data: dict, 
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    from fastapi import HTTPException
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.security import hash_password

    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == role_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    user.full_name = data.get("name", user.full_name)
    user.phone = data.get("phone", user.phone)
    user.is_active = True if data.get("status") == "Active" else False

    new_email = data.get("email")
    if new_email:
        new_email = new_email.strip().lower()
        if new_email != user.email:
            existing = await db.execute(select(User).where(User.email == new_email))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Email already exists")
            user.email = new_email

    password = data.get("password")
    if password:
        user.hashed_password = hash_password(password)

    perms = data.get("permissions", {})
    user.permissions = {
        "roleName": data.get("role", user.permissions.get("roleName") if user.permissions else "Admin"),
        "manageCourses": perms.get("manageCourses", False),
        "manageStudents": perms.get("manageStudents", False),
        "managePayments": perms.get("managePayments", False),
        "manageContent": perms.get("manageContent", False),
        "directPublish": perms.get("directPublish", False),
        "manageExams": perms.get("manageExams", False),
        "manageAdmins": perms.get("manageAdmins", False),
        "canViewRevenue": perms.get("canViewRevenue", False),
        "viewDashboard": perms.get("viewDashboard", True),
        "viewModuleStudents": perms.get("viewModuleStudents", False),
        "viewLectures": perms.get("viewLectures", False),
        "viewLoginDetails": perms.get("viewLoginDetails", False),
        "viewSiteContent": perms.get("viewSiteContent", False),
        "viewAIChatbot": perms.get("viewAIChatbot", False),
        "viewSimulator": perms.get("viewSimulator", False),
        "viewContracts": perms.get("viewContracts", False),
        "viewSettings": perms.get("viewSettings", False),
    }

    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.permissions.get("roleName"),
        "status": "Active" if user.is_active else "Inactive",
        "permissions": perms,
        "lastActive": user.updated_at.isoformat()
    }


@router.delete("/roles/{role_id}")
async def delete_admin_role(
    role_id: int, 
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    from fastapi import HTTPException
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == role_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
        
    await db.delete(user)
    await db.commit()
    return {"success": True}

@router.get("/students/{student_id}/progress")
async def get_student_progress(
    student_id: int,
    current_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed progress of a specific student for Admins."""
    from app.modules.learning.progress import get_student_progress_details
    return await get_student_progress_details(db, student_id)


@router.get("/modules/{module_id}/students")
async def get_module_students(
    module_id: int,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.courses.models import CourseModule, CourseEnrollment, ModuleStudentPolicy
    from app.modules.auth.models import User
    from sqlalchemy import select

    # Get the module
    module_stmt = select(CourseModule).where(CourseModule.id == module_id)
    module_res = await db.execute(module_stmt)
    module = module_res.scalar_one_or_none()
    if not module:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Module not found")
    
    # Get all enrollments for this module's course
    enrollments_stmt = (
        select(CourseEnrollment, User)
        .join(User, CourseEnrollment.user_id == User.id)
        .where(CourseEnrollment.course_id == module.course_id)
    )
    enrollments_res = await db.execute(enrollments_stmt)
    enrolled_students = enrollments_res.all()

    # Get existing policies for this module
    policies_stmt = select(ModuleStudentPolicy).where(ModuleStudentPolicy.module_id == module_id)
    policies_res = await db.execute(policies_stmt)
    policies = {p.student_id: p.mandatory for p in policies_res.scalars().all()}

    # Format output
    result = []
    for enrollment, user in enrolled_students:
        result.append({
            "student_id": user.id,
            "student_name": user.full_name,
            "student_email": user.email,
            "mandatory": policies.get(user.id, True) # Defaults to True (mandatory watch)
        })
    return result


@router.post("/modules/{module_id}/students-policies")
async def save_module_students_policies(
    module_id: int,
    policies_data: List[dict], # e.g. [{"student_id": 1, "mandatory": false}]
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.courses.models import ModuleStudentPolicy
    from sqlalchemy import delete
    
    # Delete existing policies first to simple upsert
    delete_stmt = delete(ModuleStudentPolicy).where(ModuleStudentPolicy.module_id == module_id)
    await db.execute(delete_stmt)

    for item in policies_data:
        policy = ModuleStudentPolicy(
            module_id=module_id,
            student_id=item["student_id"],
            mandatory=item.get("mandatory", True)
        )
        db.add(policy)
    
    await db.commit()
    return {"status": "success", "message": "Policies updated successfully"}

