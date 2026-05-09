"""Lectures module — service layer."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import selectinload

from app.modules.lectures.models import Lecture, LectureRecording
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_lecture(db: AsyncSession, data: dict) -> Lecture:
    """Admin/faculty creates a scheduled lecture."""
    lecture = Lecture(
        title=data["title"],
        description=data.get("description"),
        course_id=data["course_id"],
        instructor_id=data.get("instructor_id"),
        meeting_link=data.get("meeting_link"),
        scheduled_at=data["scheduled_at"],
        duration_minutes=data.get("duration_minutes", 60),
        max_participants=data.get("max_participants", 0),
    )
    db.add(lecture)
    await db.commit()
    
    # Reload with relationships
    query = select(Lecture).options(selectinload(Lecture.recordings)).filter(Lecture.id == lecture.id)
    result = await db.execute(query)
    lecture = result.scalar_one()
    
    logger.info("lecture_created", lecture_id=lecture.id, title=lecture.title)
    return lecture


async def list_lectures(
    db: AsyncSession, course_id: int | None = None, skip: int = 0, limit: int = 20
) -> List[Lecture]:
    """List lectures, optionally filtered by course."""
    query = (
        select(Lecture)
        .options(selectinload(Lecture.recordings))
        .offset(skip)
        .limit(limit)
        .order_by(Lecture.scheduled_at.desc())
    )
    if course_id:
        query = query.where(Lecture.course_id == course_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def join_lecture(db: AsyncSession, user_id: int, lecture_id: int) -> dict:
    """Student joins a lecture and gets the meeting link."""
    lecture = await db.get(Lecture, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    if not lecture.meeting_link:
        raise HTTPException(status_code=400, detail="Meeting link not yet available")

    logger.info("lecture_joined", user_id=user_id, lecture_id=lecture_id)
    return {
        "lecture_id": lecture.id,
        "meeting_link": lecture.meeting_link,
        "message": f"Joined lecture: {lecture.title}",
    }


async def start_lecture(db: AsyncSession, lecture_id: int) -> Lecture:
    """Start a lecture (set is_live=True)."""
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    
    lecture.is_live = True
    lecture.is_completed = False
    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_started", lecture_id=lecture.id)
    return lecture


async def end_lecture(db: AsyncSession, lecture_id: int) -> Lecture:
    """End a lecture (set is_live=False, is_completed=True)."""
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    
    lecture.is_live = False
    lecture.is_completed = True
    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_ended", lecture_id=lecture.id)
    return lecture


async def add_recording(db: AsyncSession, lecture_id: int, recording_url: str) -> LectureRecording:
    """Add a recording to a completed lecture."""
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
        
    recording = LectureRecording(
        lecture_id=lecture.id,
        recording_url=recording_url,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    logger.info("lecture_recording_added", lecture_id=lecture.id, recording_id=recording.id)
    return recording
