"""Mobile API Integration — validation schemas."""

from pydantic import BaseModel, EmailStr
from typing import Optional

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

class MobileStudentCreateRequest(BaseModel):
    user_id: str
    course_id: str
    address: str
    qualification: str

class MobileStudentCreateResponse(BaseModel):
    success: bool
    student_id: str
    message: str
