"""IB commission and wallet models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class CourseIBCommission(Base):
    __tablename__ = "course_ib_commissions"
    __table_args__ = (UniqueConstraint("course_id", "ib_id", name="uq_course_ib_commission"),)

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    ib_id = Column(Integer, ForeignKey("distributors.id", ondelete="CASCADE"), nullable=False)
    commission_type = Column(String(20), nullable=False, default="percentage")  # flat, percentage
    commission_value = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    course = relationship("Course")
    ib = relationship("Distributor")


class IBWallet(Base):
    __tablename__ = "ib_wallets"

    id = Column(Integer, primary_key=True, index=True)
    ib_id = Column(Integer, ForeignKey("distributors.id", ondelete="CASCADE"), nullable=False, unique=True)
    available_balance = Column(Float, default=0.0, nullable=False)
    total_earned = Column(Float, default=0.0, nullable=False)
    total_withdrawn = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ib = relationship("Distributor")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    ib_id = Column(Integer, ForeignKey("distributors.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    commission_amount = Column(Float, nullable=False, default=0.0)
    transaction_type = Column(String(20), nullable=False)  # credit, debit
    description = Column(Text, nullable=True)
    reference_no = Column(String(100), nullable=True, unique=True, index=True)
    status = Column(String(30), default="pending", nullable=False)  # pending, approved, paid, rejected
    balance_after = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    ib = relationship("Distributor")
    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course")


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    ib_id = Column(Integer, ForeignKey("distributors.id", ondelete="CASCADE"), nullable=False)
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
    wallet_transaction_id = Column(Integer, ForeignKey("wallet_transactions.id", ondelete="SET NULL"), nullable=True)

    ib = relationship("Distributor")
    wallet_transaction = relationship("WalletTransaction")
    proofs = relationship("PaymentProof", back_populates="withdrawal_request", cascade="all, delete-orphan")


class PaymentProof(Base):
    __tablename__ = "payment_proofs"

    id = Column(Integer, primary_key=True, index=True)
    withdrawal_request_id = Column(Integer, ForeignKey("withdrawal_requests.id", ondelete="CASCADE"), nullable=False)
    utr_number = Column(String(100), nullable=True)
    transaction_reference = Column(String(150), nullable=True)
    proof_file = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    withdrawal_request = relationship("WithdrawalRequest", back_populates="proofs")
    uploader = relationship("User")


class CommissionAuditLog(Base):
    __tablename__ = "commission_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
