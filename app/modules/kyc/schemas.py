"""KYC module — Pydantic schemas."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ── Request schemas ─────────────────────────────────────────────────

class KYCSubmitRequest(BaseModel):
    full_name: str
    dob: Optional[str] = None
    qualification: Optional[str] = None
    address: Optional[str] = None
    mobile: Optional[str] = None
    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None


class OTPVerifyRequest(BaseModel):
    otp: str = Field(..., min_length=4, max_length=6)


class KYCRejectRequest(BaseModel):
    reason: str


class ContractGenerateRequest(BaseModel):
    course_id: Optional[int] = None
    terms_accepted: bool = True


# ── Response schemas ────────────────────────────────────────────────

class KYCStatusResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    dob: Optional[str] = None
    qualification: Optional[str] = None
    address: Optional[str] = None
    mobile: Optional[str] = None
    mobile_verified: bool = False
    email_verified: bool = False
    aadhaar_number: Optional[str] = None
    aadhaar_doc_url: Optional[str] = None
    pan_number: Optional[str] = None
    pan_doc_url: Optional[str] = None
    photo_url: Optional[str] = None
    signature_url: Optional[str] = None
    biometric_selfie_url: Optional[str] = None
    status: str = "pending"
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContractResponse(BaseModel):
    id: int
    user_id: int
    kyc_id: int
    contract_number: str
    course_id: Optional[int] = None
    terms_accepted: bool = False
    signed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminKYCListItem(BaseModel):
    id: int
    user_id: int
    full_name: str
    mobile: Optional[str] = None
    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminContractListItem(BaseModel):
    id: int
    kyc_id: int
    contract_number: str
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_mobile: Optional[str] = None
    user_aadhaar: Optional[str] = None
    user_pan: Optional[str] = None
    user_dob: Optional[str] = None
    user_qualification: Optional[str] = None
    user_address: Optional[str] = None
    aadhaar_doc_url: Optional[str] = None
    pan_doc_url: Optional[str] = None
    photo_url: Optional[str] = None
    signature_url: Optional[str] = None
    biometric_selfie_url: Optional[str] = None
    kyc_status: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    course_id: Optional[int] = None
    course_title: Optional[str] = None
    signed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str
