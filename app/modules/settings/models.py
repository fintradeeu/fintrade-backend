"""Settings module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.modules.auth.models import User


from sqlalchemy.dialects.postgresql import ENUM

class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)  # Stored as JSON string
    category = Column(
        ENUM("general", "simulator", "exam", "payment", name="setting_category", create_type=False),
        default="general",
        nullable=False
    )
    label = Column(String(255), nullable=True)  # Human-readable label
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<PlatformSetting {self.key}={self.value}>"
