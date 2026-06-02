"""News module — database model."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(500), nullable=False)
    type         = Column(String(50),  nullable=False, default="Blog Story")   # "Market Update" | "Blog Story"
    description  = Column(Text,        nullable=True)
    video_url    = Column(Text,        nullable=True)   # YouTube link (Market Updates only)
    thumbnail_url= Column(Text,        nullable=True)
    status       = Column(String(50),  nullable=False, default="published")    # "published" | "draft"
    views_count  = Column(Integer,     nullable=False, default=0)
    created_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    author = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<NewsArticle id={self.id} type={self.type!r} title={self.title[:40]!r}>"
