from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.modules.auth.models import User
from app.modules.courses.models import CourseEnrollment
from app.modules.exams.models import ExamResult, EntranceExam, CourseExamResult, CourseExam

async def get_student_progress_details(db: AsyncSession, student_id: int):
    user_stmt = select(User).where(User.id == student_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Student not found")

    enroll_stmt = select(CourseEnrollment).options(
        selectinload(CourseEnrollment.course)
    ).where(CourseEnrollment.user_id == student_id)
    enroll_res = await db.execute(enroll_stmt)
    enrollments = enroll_res.scalars().all()

    enrolled_courses = []
    for e in enrollments:
        enrolled_courses.append({
            "course_id": e.course_id,
            "title": e.course.title,
            "progress_percent": e.progress_percent,
            "enrolled_at": e.enrolled_at,
            "completed_at": e.completed_at
        })

    # Entrance Exam Results
    ent_exam_stmt = select(ExamResult).options(
        selectinload(ExamResult.exam),
        selectinload(ExamResult.attempt)
    ).where(ExamResult.user_id == student_id)
    ent_exam_res = await db.execute(ent_exam_stmt)
    ent_results = ent_exam_res.scalars().all()

    # Course Exam Results
    course_exam_stmt = select(CourseExamResult).options(
        selectinload(CourseExamResult.exam),
        selectinload(CourseExamResult.attempt)
    ).where(CourseExamResult.user_id == student_id)
    course_exam_res = await db.execute(course_exam_stmt)
    course_results = course_exam_res.scalars().all()

    exam_results = []
    for r in ent_results:
        exam_results.append({
            "exam_id": r.exam_id,
            "exam_type": "entrance",
            "title": r.exam.title if r.exam else "Unknown",
            "score": r.score,
            "passed": r.passed,
            "submitted_at": r.attempt.submitted_at if hasattr(r, "attempt") and r.attempt else None
        })
        
    for r in course_results:
        exam_results.append({
            "exam_id": r.exam_id,
            "exam_type": "course",
            "title": r.exam.title if r.exam else "Unknown",
            "score": r.score,
            "passed": r.passed,
            "submitted_at": r.attempt.submitted_at if hasattr(r, "attempt") and r.attempt else None
        })

    return {
        "student_id": user.id,
        "name": user.full_name,
        "email": user.email,
        "enrolled_courses": enrolled_courses,
        "exam_results": exam_results
    }
