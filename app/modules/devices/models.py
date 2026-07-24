from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.database import Base

class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    device_id = Column(String(255), index=True, nullable=True)
    device_name = Column(String(255), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    platform = Column(String(100), nullable=True)
    os_name = Column(String(100), nullable=True)
    os_version = Column(String(100), nullable=True)
    app_version = Column(String(100), nullable=True)
    build_number = Column(String(100), nullable=True)
    language = Column(String(100), nullable=True)
    timezone = Column(String(100), nullable=True)
    screen_width = Column(Integer, nullable=True)
    screen_height = Column(Integer, nullable=True)
    fcm_token = Column(Text, nullable=True)
    network_type = Column(String(100), nullable=True)
    battery_level = Column(Float, nullable=True)
    is_emulator = Column(Boolean, default=False)
    
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_active = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", backref="mobile_devices")

class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    permission_type = Column(String(100), nullable=False) # LOCATION, NOTIFICATION, CONTACTS
    status = Column(String(100), nullable=False) # GRANTED, DENIED, NOT_ASKED
    fcm_token = Column(Text, nullable=True)
    device_id = Column(String(255), nullable=True)
    platform = Column(String(100), nullable=True)
    
    granted_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", backref="mobile_permissions")

class UserLocation(Base):
    __tablename__ = "user_locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    permission_status = Column(String(100), nullable=False) # GRANTED, DENIED
    
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(100), nullable=True)
    timezone = Column(String(100), nullable=True)
    google_maps_url = Column(Text, nullable=True)
    public_ip = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", backref="locations")

class UserContact(Base):
    __tablename__ = "user_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    permission_status = Column(String(100), nullable=False) # GRANTED, DENIED
    contact_name = Column(String(255), nullable=True)
    mobile_number = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", backref="contacts")
