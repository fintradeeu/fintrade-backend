"""Learning module — routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user, require_student_kyc
from app.modules.auth.models import User
from sqlalchemy.exc import IntegrityError
from app.modules.learning.schemas import LearningDashboardResponse, MarkLessonCompletedRequest
from app.modules.learning.services import get_user_dashboard, mark_lesson_completed

router = APIRouter(prefix="/learning", tags=["Learning"])

@router.get("/dashboard", response_model=LearningDashboardResponse)
async def read_learning_dashboard(
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db)
):
    """Get the learning dashboard data for the current user."""
    return await get_user_dashboard(db, current_user.id)

@router.post("/lesson/complete", response_model=dict)
async def complete_lesson(
    req: MarkLessonCompletedRequest,
    current_user: User = Depends(require_student_kyc),
    db: AsyncSession = Depends(get_db)
):
    """Mark a lesson as completed."""
    try:
        success = await mark_lesson_completed(db, current_user.id,req.course_id, req.lesson_id)
        return {"status": "success", "completed": success}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Invalid course or lesson ID")
