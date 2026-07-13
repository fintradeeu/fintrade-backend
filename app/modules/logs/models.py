from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from datetime import datetime, timezone
from app.db.database import Base
from sqlalchemy import JSON

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    module = Column(String(100), nullable=False) # e.g., PROFILE, AUTH, GENERAL, NAVIGATION
    action = Column(String(100), nullable=False) # e.g., PROFILE VIEW, CREATE, PAGE_VIEW
    description = Column(Text, nullable=True) # e.g., Api / Users / Profile success
    
    status_code = Column(Integer, nullable=True) # e.g. 200, 404, 500
    status_text = Column(String(50), nullable=True) # e.g. SUCCESS, FAILED
    
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Using simple JSON for dictionaries
    location_data = Column(JSON, nullable=True)
    device_data = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    
    tenant_id = Column(String(100), nullable=True)
    suspicious = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")

    def __repr__(self):
        return f"<ActivityLog {self.module} / {self.action} - {self.status_text}>"
