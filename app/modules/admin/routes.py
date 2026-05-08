"""Admin module — aggregated admin API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query
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
    course = await course_services.create_course(db, body.model_dump(), created_by=admin.id)
    return course_schemas.CourseDetailResponse.model_validate(course)


@router.put("/courses/{course_id}", response_model=course_schemas.CourseDetailResponse)
async def update_course(
    course_id: int,
    body: course_schemas.CourseUpdate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a course (admin/faculty only)."""
    course = await course_services.update_course(db, course_id, body.model_dump(exclude_unset=True))
    return course_schemas.CourseDetailResponse.model_validate(course)


@router.post("/modules", response_model=course_schemas.ModuleResponse, status_code=201)
async def create_module(
    body: course_schemas.ModuleCreate,
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a course module (admin/faculty only)."""
    module = await course_services.create_module(db, body.model_dump())
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

    # Entrance Exams
    req1 = await db.execute(select(EntranceExam).options(selectinload(EntranceExam.questions)).order_by(EntranceExam.created_at.desc()))
    entrance_exams = req1.scalars().all()
    
    # Course Exams
    req2 = await db.execute(select(CourseExam).options(selectinload(CourseExam.questions)).order_by(CourseExam.created_at.desc()))
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


@router.post("/exams/questions", response_model=schemas.MessageResponse, status_code=201)
async def add_questions(
    exam_id: int = Query(..., description="Exam to add questions to"),
    body: List[exam_schemas.ExamQuestionCreate] = ...,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Add questions to an existing exam (admin only)."""
    await exam_services.add_questions_to_exam(db, exam_id, [q.model_dump() for q in body])
    return schemas.MessageResponse(message=f"Added {len(body)} questions to exam {exam_id}")


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

