"""Feedback module — service layer."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.feedback.models import Feedback, FeedbackForm
from app.modules.courses.models import Course
from app.modules.auth.models import User


# ── Feedback Forms CRUD ───────────────────────────────────────────────

async def create_feedback_form(
    db: AsyncSession, title: str, description: Optional[str], course_id: int, is_active: bool = True
) -> FeedbackForm:
    """Create a new feedback form linked to a course."""
    import uuid
    form = FeedbackForm(
        title=title,
        description=description,
        course_id=course_id,
        is_active=is_active,
        token=str(uuid.uuid4()),
    )
    db.add(form)
    await db.flush()
    await db.refresh(form)
    return form


async def get_feedback_form(db: AsyncSession, form_id: int) -> Optional[FeedbackForm]:
    """Get feedback form details (with course loaded)."""
    result = await db.execute(
        select(FeedbackForm)
        .where(FeedbackForm.id == form_id)
        .options(selectinload(FeedbackForm.course))
    )
    form = result.scalar_one_or_none()
    
    # Self-heal missing tokens
    if form and not form.token:
        import uuid
        form.token = str(uuid.uuid4())
        await db.flush()
        await db.refresh(form)
        
    return form


async def get_feedback_form_by_token(db: AsyncSession, token: str) -> Optional[FeedbackForm]:
    """Get feedback form details by its unique token (with course loaded)."""
    result = await db.execute(
        select(FeedbackForm)
        .where(FeedbackForm.token == token)
        .options(selectinload(FeedbackForm.course))
    )
    form = result.scalar_one_or_none()
    if not form:
        # Fallback to ID lookup if the token is numeric (integer fallback)
        try:
            form_id = int(token)
            return await get_feedback_form(db, form_id)
        except ValueError:
            pass
            
    # Self-heal missing tokens if found but it doesn't have a token
    if form and not form.token:
        import uuid
        form.token = str(uuid.uuid4())
        await db.flush()
        await db.refresh(form)
        
    return form


async def list_feedback_forms(db: AsyncSession) -> List[FeedbackForm]:
    """List all feedback forms (admin view)."""
    result = await db.execute(
        select(FeedbackForm)
        .options(selectinload(FeedbackForm.course))
        .order_by(FeedbackForm.created_at.desc())
    )
    return list(result.scalars().all())


async def update_feedback_form(db: AsyncSession, form_id: int, data: dict) -> Optional[FeedbackForm]:
    """Update feedback form details."""
    form = await get_feedback_form(db, form_id)
    if not form:
        return None
    for key, val in data.items():
        if val is not None and hasattr(form, key):
            setattr(form, key, val)
    await db.flush()
    await db.refresh(form)
    return form


async def delete_feedback_form(db: AsyncSession, form_id: int) -> bool:
    """Delete a feedback form."""
    form = await get_feedback_form(db, form_id)
    if not form:
        return False
    await db.delete(form)
    await db.flush()
    return True


# ── Submissions & Moderation ──────────────────────────────────────────

async def submit_feedback(
    db: AsyncSession,
    user_id: Optional[int] = None,
    rating: int = 5,
    comments: Optional[str] = None,
    course_id: Optional[int] = None,
    form_id: Optional[int] = None,
    full_name: Optional[str] = None,
    email: Optional[str] = None,
) -> Feedback:
    """Submit feedback from a registered student or anonymous reviewer."""
    fb = Feedback(
        user_id=user_id,
        course_id=course_id,
        form_id=form_id,
        rating=rating,
        comments=comments,
        full_name=full_name,
        email=email,
        show_on_landing_page=False,
    )
    db.add(fb)
    await db.flush()
    await db.refresh(fb)
    return fb


async def list_all_feedback(db: AsyncSession) -> List[Feedback]:
    """List all feedback submissions (admin view, with details joined)."""
    result = await db.execute(
        select(Feedback)
        .options(selectinload(Feedback.course), selectinload(Feedback.user))
        .order_by(Feedback.created_at.desc())
    )
    return list(result.scalars().all())


async def list_user_feedback(db: AsyncSession, user_id: int) -> List[Feedback]:
    """List feedback submitted by a specific user."""
    result = await db.execute(
        select(Feedback)
        .where(Feedback.user_id == user_id)
        .options(selectinload(Feedback.course))
        .order_by(Feedback.created_at.desc())
    )
    return list(result.scalars().all())


async def toggle_feedback_visibility(
    db: AsyncSession, feedback_id: int, show_on_landing_page: bool
) -> Optional[Feedback]:
    """Toggle whether a review appears on the landing page."""
    result = await db.execute(
        select(Feedback)
        .where(Feedback.id == feedback_id)
        .options(selectinload(Feedback.course), selectinload(Feedback.user))
    )
    fb = result.scalar_one_or_none()
    if not fb:
        return None
    fb.show_on_landing_page = show_on_landing_page
    await db.flush()
    await db.refresh(fb)
    return fb


async def get_landing_page_feedbacks(db: AsyncSession) -> List[Feedback]:
    """Fetch all approved feedbacks to show on landing page."""
    result = await db.execute(
        select(Feedback)
        .where(Feedback.show_on_landing_page == True)
        .options(selectinload(Feedback.course))
        .order_by(Feedback.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_feedback(db: AsyncSession, feedback_id: int) -> bool:
    """Delete a feedback submission."""
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if not fb:
        return False
    await db.delete(fb)
    await db.flush()
    return True
