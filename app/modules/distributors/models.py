"""Distributors module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship, backref

from app.db.database import Base


class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    region = Column(String(255), nullable=False)
    referral_code = Column(String(50), unique=True, nullable=False, index=True)
    discount_percentage = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    user = relationship("User", backref=backref("distributor_profile", uselist=False), foreign_keys=[user_id])
    referrals = relationship("StudentReferral", back_populates="distributor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Distributor {self.referral_code}>"


class StudentReferral(Base):
    __tablename__ = "student_referrals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    distributor_id = Column(Integer, ForeignKey("distributors.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    distributor = relationship("Distributor", back_populates="referrals")
    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course", foreign_keys=[course_id])

    def __repr__(self):
        return f"<StudentReferral student={self.student_id} dist={self.distributor_id}>"
