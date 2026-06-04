"""Feedback module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    String,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class FeedbackForm(Base):
    __tablename__ = "feedback_forms"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(36), unique=True, index=True, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    course = relationship("Course")
    feedbacks = relationship("Feedback", back_populates="form", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    form_id = Column(Integer, ForeignKey("feedback_forms.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    rating = Column(Integer, nullable=False)  # 1-5
    comments = Column(Text, nullable=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    show_on_landing_page = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    form = relationship("FeedbackForm", back_populates="feedbacks")
    course = relationship("Course")
    user = relationship("User")

    def __repr__(self):
        return f"<Feedback id={self.id} rating={self.rating} show_on_landing_page={self.show_on_landing_page}>"
