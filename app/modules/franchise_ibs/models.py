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


class FranchiseIBWallet(Base):
    __tablename__ = "franchise_ib_wallets"

    id = Column(Integer, primary_key=True, index=True)
    franchise_ib_id = Column(Integer, ForeignKey("franchise_ibs.id", ondelete="CASCADE"), nullable=False, unique=True)
    available_balance = Column(Float, default=0.0, nullable=False)
    total_earned = Column(Float, default=0.0, nullable=False)
    total_withdrawn = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    franchise_ib = relationship("FranchiseIB")


class FranchiseIBWithdrawalRequest(Base):
    __tablename__ = "franchise_ib_withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    franchise_ib_id = Column(Integer, ForeignKey("franchise_ibs.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    withdrawal_method = Column(String(30), nullable=False)  # bank, upi
    account_holder_name = Column(String(255), nullable=True)
    bank_name = Column(String(255), nullable=True)
    account_number = Column(String(100), nullable=True)
    ifsc_code = Column(String(50), nullable=True)
    upi_id = Column(String(255), nullable=True)
    qr_code_image = Column(Text, nullable=True)
    status = Column(String(30), default="pending", nullable=False)  # pending, approved, paid, rejected
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    admin_remarks = Column(Text, nullable=True)
    payment_proof = Column(Text, nullable=True)
    utr_number = Column(String(100), nullable=True)
    transaction_reference = Column(String(150), nullable=True)

    franchise_ib = relationship("FranchiseIB")
