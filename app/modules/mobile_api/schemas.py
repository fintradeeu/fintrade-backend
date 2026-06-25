"""Mobile API Integration — validation schemas."""

from pydantic import BaseModel, EmailStr
from typing import Optional

# Existing schemas (keep for backwards compatibility)
class MobileUserCreateRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str

class MobileUserCreateResponse(BaseModel):
    success: bool
    user_id: str
    message: str

class UserDetails(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None

class MobileUserGetResponse(BaseModel):
    success: bool
    data: UserDetails

# Modified schemas
class MobileStudentCreateRequest(BaseModel):
    user_id: str
    course_id: Optional[str] = None  # Made optional
    address: str
    qualification: str

class MobileStudentCreateResponse(BaseModel):
    success: bool
    student_id: str
    message: str

# New Mobile Auth Schemas
class MobileSendOTPRequest(BaseModel):
    mobile: str

class MobileSendOTPResponse(BaseModel):
    success: bool
    message: str

class MobileVerifyOTPRequest(BaseModel):
    mobile: str
    otp: str

class MobileVerifyUserDetail(BaseModel):
    id: int
    first_name: str
    last_name: str
    mobile: str

class MobileVerifyOTPResponse(BaseModel):
    success: bool
    is_new_user: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[MobileVerifyUserDetail] = None
    message: Optional[str] = None

class MobileRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    mobile: str
    gender: str
    dob: str
    address: str
    qualification: str

class MobileRegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: int

# New Mobile Profile Schemas
class MobileProfileData(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    mobile: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    address: Optional[str] = None
    qualification: Optional[str] = None

class MobileProfileResponse(BaseModel):
    success: bool
    data: MobileProfileData

class MobileProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    qualification: Optional[str] = None

class MobileProfileUpdateResponse(BaseModel):
    success: bool
    message: str

# New Mobile V1 Profile Schemas
class MobileUserProfileCreateRequest(BaseModel):
    name: str
    email: EmailStr
    mobileNumber: str

class MobileUserProfileUpdateRequest(BaseModel):
    name: str
    email: EmailStr
    mobileNumber: str

class MobileUserProfileResponseData(BaseModel):
    id: str
    name: str
    email: str
    mobileNumber: str

class MobileUserProfileResponse(BaseModel):
    success: bool
    message: str
    data: MobileUserProfileResponseData

class MobileAuthMeResponse(BaseModel):
    success: bool
    data: Optional[MobileUserProfileResponseData] = None

