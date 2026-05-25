"""Auth module — Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Request schema for Google OAuth sign-in."""
    token: str = Field(..., description="Google ID token from the frontend")
    phone: Optional[str] = Field(None, max_length=20)


class ProfileUpdateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    otp_token: str
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")



class OTPVerifyRequest(BaseModel):
    """Step 2 of login — submit the OTP code."""
    otp_token: str = Field(..., description="Token returned from login step 1")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class OTPResendRequest(BaseModel):
    """Request to resend the OTP code."""
    otp_token: str = Field(..., description="Token returned from login step 1")


# ── Response schemas ─────────────────────────────────────────────────
class RoleResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    roles: List[RoleResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class OTPPendingResponse(BaseModel):
    """Returned after successful password validation — OTP has been sent."""
    message: str = "Verification code sent"
    otp_token: str
    expires_in_seconds: int
    channels: List[str] = []  # e.g. ["email", "sms"] or ["email"]


class MessageResponse(BaseModel):
    message: str
