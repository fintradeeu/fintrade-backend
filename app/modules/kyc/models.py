"""KYC module — database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class KYCSubmission(Base):
    __tablename__ = "kyc_submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Personal details
    full_name = Column(String(255), nullable=False)
    dob = Column(String(20), nullable=True)
    qualification = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)

    # Contact verification
    mobile = Column(String(20), nullable=True)
    mobile_verified = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)

    # KYC documents
    aadhaar_number = Column(String(20), nullable=True)
    aadhaar_doc_url = Column(Text, nullable=True)
    pan_number = Column(String(20), nullable=True)
    pan_doc_url = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)

    # Signature & biometric
    signature_url = Column(Text, nullable=True)
    biometric_selfie_url = Column(Text, nullable=True)

    # Status
    status = Column(
        SAEnum("pending", "verified", "rejected", name="kyc_status"),
        default="pending",
        nullable=False,
    )
    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    contracts = relationship("Contract", back_populates="kyc_submission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KYCSubmission user={self.user_id} status={self.status}>"


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kyc_id = Column(Integer, ForeignKey("kyc_submissions.id", ondelete="CASCADE"), nullable=False)
    contract_number = Column(String(50), unique=True, nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    terms_accepted = Column(Boolean, default=False)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    contract_text = Column(Text, nullable=True)  # Stored contract content
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    kyc_submission = relationship("KYCSubmission", back_populates="contracts")

    def __repr__(self):
        return f"<Contract {self.contract_number}>"
