"""Roles module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    admin_role = Column(String(50), nullable=False, default="support_admin")
    manage_courses = Column(Boolean, default=False)
    manage_students = Column(Boolean, default=False)
    manage_payments = Column(Boolean, default=False)
    manage_content = Column(Boolean, default=False)
    manage_exams = Column(Boolean, default=False)
    manage_admins = Column(Boolean, default=False)
    can_view_revenue = Column(Boolean, default=False)
    status = Column(String(20), default="Active")
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AdminPermission user={self.user_id} role={self.admin_role}>"
