"""Exams module — API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.exams import schemas, services

router = APIRouter(prefix="/exams", tags=["Entrance Exams"])


@router.get("/entrance", response_model=List[schemas.EntranceExamResponse])
async def list_entrance_exams(db: AsyncSession = Depends(get_db)):
    """List all active entrance exams."""
    exams = await services.get_entrance_exams(db)
    return [schemas.EntranceExamResponse.model_validate(e) for e in exams]

@router.get("/all")
async def list_all_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all exams with student's attempt history."""
    from app.modules.exams.models import CourseExam, CourseExamAttempt, EntranceExam, ExamAttempt, ExamViolation
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Fetch Entrance Exams + Student attempts
        ent_res = await db.execute(
            select(EntranceExam).options(selectinload(EntranceExam.questions))
        )
        entrance = ent_res.scalars().all()

        ent_attempts_res = await db.execute(
            select(ExamAttempt).options(selectinload(ExamAttempt.result))
            .where(ExamAttempt.user_id == current_user.id)
        )
        ent_attempts = ent_attempts_res.scalars().all()
        ent_history = {}
        for a in ent_attempts:
            if a.exam_id not in ent_history: ent_history[a.exam_id] = []
            ent_history[a.exam_id].append({
                "id": a.id,
                "submitted_at": a.submitted_at,
                "percentage": a.result.percentage if a.result else 0,
                "passed": a.result.passed if a.result else False,
                "is_violation_wasted": False
            })

        # Fetch Course Exams + Student attempts
        course_res = await db.execute(
            select(CourseExam).options(selectinload(CourseExam.questions))
        )
        course_exams = course_res.scalars().all()

        course_attempts_res = await db.execute(
            select(CourseExamAttempt).options(selectinload(CourseExamAttempt.result), selectinload(CourseExamAttempt.violations))
            .where(CourseExamAttempt.user_id == current_user.id)
        )
        course_attempts = course_attempts_res.scalars().all()
        course_history = {}
        for a in course_attempts:
            if a.exam_id not in course_history: course_history[a.exam_id] = []
            is_violation_wasted = any(v.violation_type == "tab_switch" for v in a.violations)
            course_history[a.exam_id].append({
                "id": a.id,
                "submitted_at": a.submitted_at,
                "percentage": a.result.percentage if a.result else 0,
                "passed": a.result.passed if a.result else False,
                "is_violation_wasted": is_violation_wasted
            })

        return {
            "entrance_exams": [
                {
                    "id": e.id,
                    "title": e.title,
                    "type": "entrance",
                    "questions_count": len(e.questions),
                    "duration_minutes": e.duration_minutes,
                    "passing_score": e.passing_score,
                    "is_active": e.is_active,
                    "course_id": e.course_id,
                    "attempts": ent_history.get(e.id, [])
                } for e in entrance
            ],
            "course_exams": [
                {
                    "id": e.id,
                    "title": e.title,
                    "type": e.exam_type,
                    "questions_count": len(e.questions),
                    "duration_minutes": e.duration_minutes,
                    "passing_score": e.passing_score,
                    "is_active": e.is_active,
                    "course_id": e.course_id,
                    "module_id": e.module_id,
                    "attempts": course_history.get(e.id, [])
                } for e in course_exams
            ]
        }
    except Exception as e:
        logger.error(f"Error in student list_all_exams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/start", response_model=schemas.AttemptStartResponse)
async def start_exam(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new exam attempt (enforces 30-day restriction)."""
    result = await services.start_exam(db, current_user.id, exam_id)
    return result


@router.get("/questions", response_model=List[schemas.ExamQuestionResponse])
async def get_questions(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get questions for the current active entrance exam attempt (correct answers hidden)."""
    questions = await services.get_exam_questions(db, current_user.id, exam_id)
    return [schemas.ExamQuestionResponse.model_validate(q) for q in questions]


@router.get("/course/questions", response_model=List[schemas.ExamQuestionResponse])
async def get_course_questions(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get questions for the current active course exam attempt (correct answers hidden)."""
    questions = await services.get_course_exam_questions(db, current_user.id, exam_id)
    return [schemas.ExamQuestionResponse.model_validate(q) for q in questions]


@router.post("/answer", response_model=schemas.MessageResponse)
async def save_answer(
    body: schemas.AnswerSubmit,
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an individual answer during the exam."""
    await services.save_answer(
        db, current_user.id, attempt_id, body.question_id, body.selected_option_id
    )
    return schemas.MessageResponse(message="Answer saved")


@router.post("/submit", response_model=schemas.ExamResultResponse)
async def submit_exam(
    body: schemas.ExamSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit the entrance exam, auto-evaluate, and return the result."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        answers = [{"question_id": a.question_id, "selected_option_id": a.selected_option_id} for a in body.answers]
        result = await services.submit_exam(db, current_user.id, body.attempt_id, answers)
        return schemas.ExamResultResponse.model_validate(result)
    except Exception as e:
        logger.error(f"Error in submit_exam: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/course/submit", response_model=schemas.ExamResultResponse)
async def submit_course_exam(
    body: schemas.ExamSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit the course exam, auto-evaluate, and return the result."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        answers = [{"question_id": a.question_id, "selected_option_id": a.selected_option_id, "descriptive_text": a.descriptive_text} for a in body.answers]
        result = await services.submit_course_exam(db, current_user.id, body.attempt_id, answers)
        return schemas.ExamResultResponse.model_validate(result)
    except Exception as e:
        logger.error(f"Error in submit_course_exam: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/result", response_model=schemas.ExamResultResponse)
async def get_result(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent entrance exam result."""
    result = await services.get_exam_result(db, current_user.id, exam_id)
    return schemas.ExamResultResponse.model_validate(result)

@router.get("/course/result", response_model=schemas.ExamResultResponse)
async def get_course_result(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent course exam result."""
    result = await services.get_course_exam_result(db, current_user.id, exam_id)
    return schemas.ExamResultResponse.model_validate(result)

# ── Phase 2 Routes ───────────────────────────────────────────────────

@router.get("/monthly", response_model=List[schemas.MonthlyExamResponse])
async def list_monthly_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    exams = await services.get_monthly_exams(db, current_user.id)
    return [schemas.MonthlyExamResponse.model_validate(e) for e in exams]

@router.post("/pay", response_model=schemas.MessageResponse)
async def pay_exam_fee(
    req: schemas.ExamPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await services.process_exam_payment(db, current_user.id, req.exam_id, req.amount)
        return schemas.MessageResponse(message="Payment processed successfully")
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Invalid exam ID")

@router.post("/course/start", response_model=schemas.AttemptCourseStartResponse)
async def start_course_exam(
    exam_id: int,
    req: schemas.ExamStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    out = await services.start_course_exam(db, current_user.id, exam_id, req.device_id)
    return schemas.AttemptCourseStartResponse.model_validate(out)

@router.post("/violation", response_model=schemas.MessageResponse)
async def log_violation(
    req: schemas.ExamViolationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await services.log_exam_violation(db, current_user.id, req.attempt_id, req.violation_type)
        return schemas.MessageResponse(message="Violation logged")
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Invalid attempt ID")

@router.post("/camera-status", response_model=schemas.MessageResponse)
async def camera_status(
    req: schemas.CameraStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        if not req.camera_on:
            await services.log_exam_violation(db, current_user.id, req.attempt_id, "camera_off")
        return schemas.MessageResponse(message="Status logged")
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Invalid attempt ID")

@router.post("/session-close", response_model=schemas.MessageResponse)
async def session_close(
    req: schemas.SessionCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await services.close_exam_session(db, current_user.id, req.attempt_id)
    return schemas.MessageResponse(message="Session closed")


# ── Skill-Based Result Analysis ──────────────────────────────────────

@router.get("/results/analysis", response_model=schemas.SkillAnalysisResponse)
async def get_skill_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get skill-based result analysis with strong/weak areas."""
    data = await services.get_skill_analysis(db, current_user.id)
    return schemas.SkillAnalysisResponse(**data)

@router.get("/course/attempt/{attempt_id}/review", response_model=schemas.AttemptReviewResponse)
async def get_course_attempt_review(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed review for a course exam attempt."""
    return await services.get_course_exam_attempt_review(db, current_user.id, attempt_id)

@router.get("/entrance/attempt/{attempt_id}/review", response_model=schemas.AttemptReviewResponse)
async def get_entrance_attempt_review(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed review for an entrance exam attempt."""
    return await services.get_entrance_exam_attempt_review(db, current_user.id, attempt_id)

