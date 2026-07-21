"""Franchise IBs module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, backref

from app.db.database import Base


class FranchiseIB(Base):
    __tablename__ = "franchise_ibs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    referral_code = Column(String(50), unique=True, nullable=False, index=True)
    
    pan_card_url = Column(Text, nullable=True)
    pan_number = Column(String(50), nullable=True)
    aadhaar_card_url = Column(Text, nullable=True)
    aadhaar_number = Column(String(50), nullable=True)
    
    bank_account_holder_name = Column(String(255), nullable=True)
    bank_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    bank_ifsc_code = Column(String(50), nullable=True)
    
    cancelled_cheque_url = Column(Text, nullable=True)
    
    self_registered = Column(String(10), nullable=False, default="no")
    verification_status = Column(String(30), nullable=False, default="pending")
    commission_percentage = Column(Float, nullable=False, default=100.0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    user = relationship("User", backref=backref("franchise_ib_profile", uselist=False), foreign_keys=[user_id])
    distributors = relationship("Distributor", back_populates="franchise", cascade="all, delete-orphan")
    direct_referrals = relationship("StudentReferral", back_populates="franchise_ib", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FranchiseIB {self.referral_code}>"
