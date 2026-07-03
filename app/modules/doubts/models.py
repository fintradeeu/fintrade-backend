"""Doubts module — database models."""

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


class DoubtForm(Base):
    """A time-boxed doubt-collection form created by admin or faculty."""

    __tablename__ = "doubt_forms"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    batch = relationship("Batch")
    creator = relationship("User", foreign_keys=[created_by])
    submissions = relationship("DoubtSubmission", back_populates="form", cascade="all, delete-orphan")


class DoubtSubmission(Base):
    """A single student doubt submitted against a DoubtForm."""

    __tablename__ = "doubt_submissions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("doubt_forms.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(255), nullable=True)
    doubt_text = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    form = relationship("DoubtForm", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id])
