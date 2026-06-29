"""Auth module — Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional, Any

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Request schemas ──────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    referral_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email Address or Mobile Number")
    password: str


class GoogleAuthRequest(BaseModel):
    """Request schema for Google OAuth sign-in."""
    token: Optional[str] = Field(None, description="Google ID token from the frontend")
    access_token: Optional[str] = Field(None, description="Google access token from the frontend")
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)


class GoogleProfileCompletionRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Email Address or Mobile Number")


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


class OTPCancelRequest(BaseModel):
    """Request to cancel registration/verify-otp session."""
    otp_token: str = Field(..., description="Token returned from registration")


# ── Response schemas ─────────────────────────────────────────────────
class RoleResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class DistributorProfileResponse(BaseModel):
    region: str
    referral_code: str
    discount_percentage: float

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    city: Optional[str] = None
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    permissions: Optional[dict] = None
    has_password: bool = False
    roles: List[RoleResponse] = []
    distributor_profile: Optional[DistributorProfileResponse] = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def check_relationships(cls, data: Any) -> Any:
        if hasattr(data, "_sa_instance_state"):
            res = {
                "id": data.id,
                "email": data.email,
                "full_name": data.full_name,
                "phone": data.phone,
                "city": data.city,
                "is_active": data.is_active,
                "is_verified": data.is_verified,
                "avatar_url": data.avatar_url,
                "permissions": data.permissions,
                "has_password": bool(data.hashed_password),
                "created_at": data.created_at,
            }
            if "roles" in data.__dict__:
                res["roles"] = data.roles
            else:
                res["roles"] = []
            if "distributor_profile" in data.__dict__:
                profile = data.distributor_profile
                # Handle case where it is loaded as an InstrumentedList or list
                if isinstance(profile, list) or hasattr(profile, "__iter__") and not isinstance(profile, (str, dict)):
                    profile_list = list(profile)
                    res["distributor_profile"] = profile_list[0] if profile_list else None
                else:
                    res["distributor_profile"] = profile
            else:
                res["distributor_profile"] = None
            return res
        return data

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


class CookieConsentCreate(BaseModel):
    consent_type: Optional[str] = "accepted"


class CookieConsentResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_type: str
    created_at: datetime
    user_email: Optional[str] = None
    user_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_user_details(cls, data: Any) -> Any:
        if hasattr(data, "user") and data.user:
            # For ORM objects
            data.user_email = data.user.email
            data.user_name = data.user.full_name
        elif isinstance(data, dict) and "user" in data and data["user"]:
            # For dictionaries
            user_obj = data["user"]
            if hasattr(user_obj, "email"):
                data["user_email"] = user_obj.email
                data["user_name"] = user_obj.full_name
            elif isinstance(user_obj, dict):
                data["user_email"] = user_obj.get("email")
                data["user_name"] = user_obj.get("full_name")
        return data

    model_config = {"from_attributes": True}
