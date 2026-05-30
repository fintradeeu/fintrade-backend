"""News module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    type = Column(String(50), default="Blog Story", nullable=False)
    description = Column(Text, nullable=True)
    video_type = Column(
        Enum("youtube", "uploaded", name="video_type"),
        default="youtube",
        nullable=False,
    )
    video_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    status = Column(
        Enum("published", "draft", name="news_status"),
        default="published",
        nullable=False,
    )
    views_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    author = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<NewsArticle {self.title[:30]}>"
