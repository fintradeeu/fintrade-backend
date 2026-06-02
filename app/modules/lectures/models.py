"""Lectures module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Lecture(Base):
    __tablename__ = "lectures"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    meeting_link = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=60)
    is_live = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)
    max_participants = Column(Integer, default=0)  # 0 = unlimited
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    recordings = relationship("LectureRecording", back_populates="lecture", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lecture {self.title}>"


class LectureRecording(Base):
    __tablename__ = "lecture_recordings"

    id = Column(Integer, primary_key=True, index=True)
    lecture_id = Column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    recording_url = Column(Text, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    file_size_mb = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    lecture = relationship("Lecture", back_populates="recordings")

    def __repr__(self):
        return f"<LectureRecording lecture={self.lecture_id}>"
