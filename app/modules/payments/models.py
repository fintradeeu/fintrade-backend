"""Payments module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    
    txnid = Column(String(100), unique=True, index=True, nullable=False)
    easepayid = Column(String(100), nullable=True)
    
    amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending", nullable=False) # pending, success, failed
    payment_mode = Column(String(50), nullable=True)
    coupon_code = Column(String(100), nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="SET NULL"), nullable=True)
    gateway_response = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Offline payment specific fields
    reference_number = Column(String(255), nullable=True) # Receipt number or Cheque number
    payment_date = Column(DateTime(timezone=True), nullable=True)
    bank_name = Column(String(255), nullable=True)
    branch_name = Column(String(255), nullable=True)
    account_holder_name = Column(String(255), nullable=True)
    cheque_image_url = Column(String(500), nullable=True)
    remarks = Column(String(1000), nullable=True)

