from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
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
    log_metadata = relationship("ActivityLogMetadata", back_populates="activity_log", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ActivityLog {self.module} / {self.action} - {self.status_text}>"

class ActivityLogMetadata(Base):
    __tablename__ = "activity_log_metadata"

    id = Column(Integer, primary_key=True, index=True)
    activity_log_id = Column(Integer, ForeignKey("activity_logs.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    referrer = Column(String(500), nullable=True)
    user_agent = Column(Text, nullable=True)
    browser = Column(String(100), nullable=True)
    browser_version = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    os_version = Column(String(100), nullable=True)
    device_type = Column(String(100), nullable=True)
    screen_width = Column(Integer, nullable=True)
    screen_height = Column(Integer, nullable=True)
    language = Column(String(50), nullable=True)
    timezone = Column(String(100), nullable=True)
    
    ip_address = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(50), nullable=True)
    
    permission_status = Column(String(100), nullable=True) # LOCATION, NOTIFICATION status when logged
    app_version = Column(String(100), nullable=True)
    build_number = Column(String(100), nullable=True)
    
    activity_log = relationship("ActivityLog", back_populates="log_metadata")
