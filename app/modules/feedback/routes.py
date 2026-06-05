"""Feedback module — API routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from jose import jwt

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.config import settings
from app.modules.auth.models import User, Session as UserSession
from app.modules.feedback import schemas, services

router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ── Optional Current User helper (for public submissions) ─────────────

async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        # Verify session is still valid
        session_result = await db.execute(
            select(UserSession).where(
                UserSession.user_id == int(user_id),
                UserSession.token == token,
                UserSession.is_active == True,
            )
        )
        session_obj = session_result.scalar_one_or_none()
        if session_obj is None:
            return None

        result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == int(user_id), User.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


# ── Feedback Forms CRUD (Admin only) ──────────────────────────────────

@router.post("/forms", response_model=schemas.FeedbackFormResponse, status_code=201)
async def create_form(
    req: schemas.FeedbackFormCreateRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Create a new feedback form linked to a course."""
    form = await services.create_feedback_form(
        db, title=req.title, description=req.description, course_id=req.course_id, is_active=req.is_active
    )
    # Load course detail to satisfy schemas.FeedbackFormResponse
    from app.modules.courses.models import Course
    course = await db.get(Course, form.course_id)
    form_res = schemas.FeedbackFormResponse.model_validate(form)
    form_res.course_title = course.title if course else None
    return form_res


@router.get("/forms", response_model=List[schemas.FeedbackFormResponse])
async def list_forms(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """List all feedback forms (admin only)."""
    forms = await services.list_feedback_forms(db)
    res = []
    for f in forms:
        item = schemas.FeedbackFormResponse.model_validate(f)
        item.course_title = f.course.title if f.course else None
        res.append(item)
    return res


@router.get("/forms/{id}", response_model=schemas.FeedbackFormResponse)
async def get_form(
    id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Fetch single feedback form details."""
    f = await services.get_feedback_form(db, id)
    if not f:
        raise HTTPException(status_code=404, detail="Form not found")
    item = schemas.FeedbackFormResponse.model_validate(f)
    item.course_title = f.course.title if f.course else None
    return item


@router.put("/forms/{id}", response_model=schemas.FeedbackFormResponse)
async def update_form(
    id: int,
    req: schemas.FeedbackFormUpdateRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Update feedback form details/status."""
    f = await services.update_feedback_form(db, id, req.model_dump(exclude_unset=True))
    if not f:
        raise HTTPException(status_code=404, detail="Form not found")
    item = schemas.FeedbackFormResponse.model_validate(f)
    item.course_title = f.course.title if f.course else None
    return item


@router.delete("/forms/{id}", response_model=schemas.MessageResponse)
async def delete_form(
    id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Delete a feedback form."""
    success = await services.delete_feedback_form(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Form not found")
    return {"message": "Form deleted successfully"}


# ── Public / Shareable Page Endpoints ─────────────────────────────────

@router.get("/forms/public/{form_key}")
async def get_public_form(
    form_key: str,
    db: AsyncSession = Depends(get_db)
):
    """Fetch public details of a feedback form (includes linked course name and description)."""
    from app.modules.courses.models import Course
    f = await services.get_feedback_form_by_token(db, form_key)
    if not f or not f.is_active:
        raise HTTPException(status_code=404, detail="Feedback form is not active or not found")
    
    # Load course detail for public rendering
    course = await db.get(Course, f.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course linked to this form not found")
        
    return {
        "id": f.id,
        "token": f.token,
        "title": f.title,
        "description": f.description,
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "short_description": course.short_description,
            "thumbnail_url": course.thumbnail_url
        }
    }


@router.post("/submit", response_model=schemas.FeedbackResponse, status_code=201)
async def submit_public_feedback(
    req: schemas.FeedbackCreateRequest,
    db: AsyncSession = Depends(get_db),
    opt_user: Optional[User] = Depends(get_optional_user)
):
    """Submit anonymous or student feedback for a course/form."""
    if not req.course_id and not req.form_id:
        raise HTTPException(status_code=400, detail="Either course_id or form_id must be provided")
        
    c_id = req.course_id
    if req.form_id:
        f = await services.get_feedback_form(db, req.form_id)
        if f:
            c_id = f.course_id
            
    user_id = opt_user.id if opt_user else None
    full_name = req.full_name
    email = req.email
    
    if opt_user:
        full_name = opt_user.full_name
        email = opt_user.email
        
    fb = await services.submit_feedback(
        db,
        user_id=user_id,
        rating=req.rating,
        comments=req.comments,
        course_id=c_id,
        form_id=req.form_id,
        full_name=full_name,
        email=email
    )
    await db.commit()
    
    # Convert to schema response
    res = schemas.FeedbackResponse.model_validate(fb)
    res.user_name = full_name
    from app.modules.courses.models import Course
    course = await db.get(Course, c_id) if c_id else None
    res.course_title = course.title if course else None
    return res


# ── Submissions Administration & Moderation (Admin only) ──────────────

@router.get("", response_model=List[schemas.FeedbackResponse])
async def list_feedback(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback submissions."""
    items = await services.list_all_feedback(db)
    res = []
    for f in items:
        item = schemas.FeedbackResponse.model_validate(f)
        item.course_title = f.course.title if f.course else None
        item.user_name = f.full_name or (f.user.full_name if f.user else "Anonymous")
        res.append(item)
    return res


@router.put("/{id}/toggle-visibility", response_model=schemas.FeedbackResponse)
async def toggle_visibility(
    id: int,
    show_on_landing_page: bool,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Toggle whether a review appears on the public landing page."""
    fb = await services.toggle_feedback_visibility(db, id, show_on_landing_page)
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.commit()
    
    res = schemas.FeedbackResponse.model_validate(fb)
    res.user_name = fb.full_name or (fb.user.full_name if fb.user else "Anonymous")
    res.course_title = fb.course.title if fb.course else None
    return res


@router.delete("/{id}", response_model=schemas.MessageResponse)
async def delete_submitted_feedback(
    id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Delete a feedback submission from the database."""
    success = await services.delete_feedback(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.commit()
    return {"message": "Feedback deleted successfully"}


# ── Public Landing Page Fetch ─────────────────────────────────────────

@router.get("/landing", response_model=List[schemas.FeedbackResponse])
async def landing_feedback(
    db: AsyncSession = Depends(get_db)
):
    """Fetch all approved testimonials to render in the landing page slider."""
    items = await services.get_landing_page_feedbacks(db)
    res = []
    for f in items:
        item = schemas.FeedbackResponse.model_validate(f)
        item.course_title = f.course.title if f.course else None
        item.user_name = f.full_name or (f.user.full_name if f.user else "Anonymous")
        res.append(item)
    return res


@router.get("/my", response_model=List[schemas.FeedbackResponse])
async def my_feedback(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List feedback submitted by current logged-in user."""
    items = await services.list_user_feedback(db, current_user.id)
    return [schemas.FeedbackResponse.model_validate(f) for f in items]
