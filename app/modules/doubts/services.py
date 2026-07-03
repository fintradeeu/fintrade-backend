"""Doubts module — async service layer."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.doubts.models import DoubtForm, DoubtSubmission
from app.modules.batches.models import StudentBatchEnrollment


async def create_doubt_form(db: AsyncSession, data: dict, creator_id: int) -> DoubtForm:
    """Create a new doubt form."""
    form = DoubtForm(**data, created_by=creator_id)
    db.add(form)
    await db.commit()
    await db.refresh(form)
    # Reload with relationships
    result = await db.execute(
        select(DoubtForm)
        .options(selectinload(DoubtForm.batch), selectinload(DoubtForm.submissions))
        .where(DoubtForm.id == form.id)
    )
    return result.scalar_one()


async def list_doubt_forms(db: AsyncSession) -> List[DoubtForm]:
    """List all doubt forms with batch and submission count info."""
    result = await db.execute(
        select(DoubtForm)
        .options(selectinload(DoubtForm.batch), selectinload(DoubtForm.submissions))
        .order_by(DoubtForm.created_at.desc())
    )
    return result.scalars().all()


async def get_doubt_form(db: AsyncSession, form_id: int) -> Optional[DoubtForm]:
    """Get a single doubt form by ID."""
    result = await db.execute(
        select(DoubtForm)
        .options(selectinload(DoubtForm.batch), selectinload(DoubtForm.submissions))
        .where(DoubtForm.id == form_id)
    )
    return result.scalar_one_or_none()


async def update_doubt_form(db: AsyncSession, form_id: int, data: dict) -> Optional[DoubtForm]:
    """Update a doubt form."""
    form = await db.get(DoubtForm, form_id)
    if not form:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(form, key, value)
    form.updated_at = datetime.now(timezone.utc)
    await db.commit()
    result = await db.execute(
        select(DoubtForm)
        .options(selectinload(DoubtForm.batch), selectinload(DoubtForm.submissions))
        .where(DoubtForm.id == form_id)
    )
    return result.scalar_one()


async def delete_doubt_form(db: AsyncSession, form_id: int) -> bool:
    """Delete a doubt form."""
    form = await db.get(DoubtForm, form_id)
    if not form:
        return False
    await db.delete(form)
    await db.commit()
    return True


async def get_forms_for_student(db: AsyncSession, student_id: int) -> List[DoubtForm]:
    """Get active, non-expired doubt forms for the student's enrolled batches."""
    now = datetime.now(timezone.utc)

    # Get the batch IDs the student is enrolled in
    enrollment_result = await db.execute(
        select(StudentBatchEnrollment.batch_id)
        .where(
            StudentBatchEnrollment.user_id == student_id,
            StudentBatchEnrollment.is_active == True,
        )
    )
    batch_ids = [row[0] for row in enrollment_result.all()]

    if not batch_ids:
        return []

    result = await db.execute(
        select(DoubtForm)
        .options(selectinload(DoubtForm.batch))
        .where(
            DoubtForm.batch_id.in_(batch_ids),
            DoubtForm.is_active == True,
            DoubtForm.end_date > now,
        )
        .order_by(DoubtForm.end_date.asc())
    )
    return result.scalars().all()


async def has_student_submitted(db: AsyncSession, form_id: int, student_id: int) -> bool:
    """Check if a student already submitted a doubt for the given form."""
    result = await db.execute(
        select(func.count()).where(
            DoubtSubmission.form_id == form_id,
            DoubtSubmission.student_id == student_id,
        )
    )
    return result.scalar() > 0


async def submit_doubt(db: AsyncSession, form_id: int, student_id: int, data: dict) -> DoubtSubmission:
    """Submit a doubt for a form."""
    submission = DoubtSubmission(form_id=form_id, student_id=student_id, **data)
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    result = await db.execute(
        select(DoubtSubmission)
        .options(selectinload(DoubtSubmission.student))
        .where(DoubtSubmission.id == submission.id)
    )
    return result.scalar_one()


async def get_form_submissions(db: AsyncSession, form_id: int) -> List[DoubtSubmission]:
    """Get all submissions for a doubt form."""
    result = await db.execute(
        select(DoubtSubmission)
        .options(selectinload(DoubtSubmission.student))
        .where(DoubtSubmission.form_id == form_id)
        .order_by(DoubtSubmission.submitted_at.desc())
    )
    return result.scalars().all()
