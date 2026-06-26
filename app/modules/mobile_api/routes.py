"""Mobile API Integration — routes."""

import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.database import get_db
from app.core.security import get_current_user
from app.core.twilio_otp import clean_phone_number
from app.modules.auth.models import User, Role, Student, MobileOTPCode
from app.modules.courses.models import CourseEnrollment
from app.modules.mobile_api import schemas

router = APIRouter(prefix="/users", tags=["Mobile API"])

@router.post("", response_model=schemas.MobileUserCreateResponse, status_code=201)
async def create_mobile_user(
    body: schemas.MobileUserCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user or update details if already exists by email."""
    email = body.email.strip().lower()
    first_name = body.first_name.strip()
    last_name = body.last_name.strip()
    phone = body.phone.strip()
    full_name = f"{first_name} {last_name}".strip()

    # Check if user already exists
    existing_user = await db.scalar(
        select(User).where(User.email == email)
    )
    if existing_user:
        # Update details
        existing_user.full_name = full_name
        existing_user.phone = phone
        await db.commit()
        return schemas.MobileUserCreateResponse(
            success=True,
            user_id=str(existing_user.id),
            message="User updated successfully"
        )

    # Create new user
    new_user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return schemas.MobileUserCreateResponse(
        success=True,
        user_id=str(new_user.id),
        message="User created successfully"
    )

@router.get("/{user_id}", response_model=schemas.MobileUserGetResponse)
async def get_mobile_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve user details by user ID and split full_name into first/last name."""
    try:
        u_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await db.get(User, u_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    parts = (user.full_name or "").split(" ", 1)
    first_name = parts[0] if len(parts) > 0 else ""
    last_name = parts[1] if len(parts) > 1 else ""

    data = schemas.UserDetails(
        first_name=first_name,
        last_name=last_name,
        email=user.email,
        phone=user.phone
    )

    return schemas.MobileUserGetResponse(
        success=True,
        data=data
    )


student_router = APIRouter(prefix="/students", tags=["Mobile API"])

@student_router.post("", response_model=schemas.MobileStudentCreateResponse, status_code=201)
async def create_mobile_student(
    body: schemas.MobileStudentCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a student profile linked to a user and assign the student role (no enrollment)."""
    try:
        u_id = int(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    try:
        c_id = int(body.course_id) if body.course_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    # Fetch User
    user = await db.get(User, u_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Add the student role if not already assigned
    student_role = await db.scalar(
        select(Role).where(Role.name == "student")
    )
    if student_role and student_role not in user.roles:
        user.roles.append(student_role)

    # Check if Student profile already exists
    student = await db.scalar(
        select(Student).where(Student.user_id == u_id)
    )
    if student:
        # Update details
        student.course_id = c_id
        student.address = body.address
        student.qualification = body.qualification
    else:
        # Create student profile
        student = Student(
            user_id=u_id,
            course_id=c_id,
            address=body.address,
            qualification=body.qualification
        )
        db.add(student)

    # Auto-enrollment logic has been removed to support on-demand purchase / enrollment
    await db.commit()
    await db.refresh(student)

    return schemas.MobileStudentCreateResponse(
        success=True,
        student_id=str(student.id),
        message="Student created successfully"
    )


# Dedicated Mobile Auth router
mobile_auth_router = APIRouter(prefix="/mobile/auth", tags=["Mobile Auth"])

@mobile_auth_router.post("/send-otp", response_model=schemas.MobileSendOTPResponse)
async def mobile_send_otp(
    body: schemas.MobileSendOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send verification OTP using SMS gateways or fallback in development."""
    mobile = body.mobile.strip()
    if not mobile or len(mobile) < 10:
        raise HTTPException(status_code=400, detail="Invalid mobile number format")

    cleaned_mobile = clean_phone_number(mobile)
    
    # Generate OTP code (6 digits)
    otp_code = "".join(secrets.choice(string.digits) for _ in range(6))
    otp_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    sms_sent = False
    
    # 1. Twilio Verify (if configured)
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_SERVICE_SID:
        try:
            from app.core.twilio_otp import send_twilio_otp
            sms_sent = await send_twilio_otp(cleaned_mobile)
            otp_code = "000000"  # Dummy code stored in DB for Twilio Verify
        except Exception:
            pass

    # 2. Nimbus SMS (if configured and Twilio verify skipped/failed)
    if not sms_sent and settings.NIMBUS_SMS_USER_ID and settings.NIMBUS_SMS_PASSWORD:
        try:
            from app.core.nimbus_sms import send_nimbus_sms
            from app.utils.aws_notifications import build_otp_sms_message
            sms_msg = build_otp_sms_message(otp_code)
            sms_sent = await send_nimbus_sms(cleaned_mobile, sms_msg)
        except Exception:
            pass

    # Development/Testing fallback
    if not sms_sent:
        print(f"\n[DEVELOPMENT ONLY] Mobile OTP for {cleaned_mobile} is {otp_code} (Token: {otp_token})\n")

    # Save to database
    db_otp = MobileOTPCode(
        mobile=cleaned_mobile,
        code=otp_code,
        otp_token=otp_token,
        expires_at=expires_at,
        is_used=False,
        attempts=0
    )
    db.add(db_otp)
    await db.commit()

    return schemas.MobileSendOTPResponse(
        success=True,
        message="OTP sent successfully"
    )

@mobile_auth_router.post("/verify-otp", response_model=schemas.MobileVerifyOTPResponse)
async def mobile_verify_otp(
    body: schemas.MobileVerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Verify OTP and return authentication tokens if the user exists, or prompt registration."""
    mobile = body.mobile.strip()
    otp_code = body.otp.strip()
    cleaned_mobile = clean_phone_number(mobile)

    # Fetch the latest OTP session for this number
    result = await db.execute(
        select(MobileOTPCode)
        .where(MobileOTPCode.mobile == cleaned_mobile)
        .order_by(MobileOTPCode.created_at.desc())
    )
    db_otp = result.scalars().first()

    if not db_otp:
        raise HTTPException(status_code=400, detail="No OTP session found for this mobile number.")

    if db_otp.is_used:
        raise HTTPException(status_code=400, detail="This verification code has already been used.")

    if datetime.now(timezone.utc) > db_otp.expires_at:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    if db_otp.attempts >= 5:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new code.")

    # Validate OTP code
    is_valid = False
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_SERVICE_SID:
        try:
            from app.core.twilio_otp import check_twilio_otp
            is_valid = await check_twilio_otp(cleaned_mobile, otp_code)
        except Exception:
            is_valid = False
    else:
        is_valid = (db_otp.code == otp_code)

    if not is_valid:
        db_otp.attempts += 1
        await db.commit()
        remaining = 5 - db_otp.attempts
        raise HTTPException(
            status_code=400,
            detail=f"Incorrect verification code. {remaining} attempt(s) remaining."
        )

    # Mark OTP session as verified
    db_otp.is_used = True
    await db.commit()

    # Retrieve user by mobile
    last_digits = cleaned_mobile[-10:]
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where((User.phone == cleaned_mobile) | (User.phone.like(f"%{last_digits}")))
    )
    user = user_result.scalar_one_or_none()

    if not user:
        return schemas.MobileVerifyOTPResponse(
            success=True,
            is_new_user=True,
            message="Complete registration"
        )

    # User exists: Log them in and generate session
    from app.modules.auth import services as auth_services
    tokens = await auth_services.create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    await db.commit()

    parts = (user.full_name or "").split(" ", 1)
    first_name = parts[0] if len(parts) > 0 else ""
    last_name = parts[1] if len(parts) > 1 else ""

    return schemas.MobileVerifyOTPResponse(
        success=True,
        is_new_user=False,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=schemas.MobileVerifyUserDetail(
            id=user.id,
            first_name=first_name,
            last_name=last_name,
            mobile=user.phone or mobile
        )
    )

@mobile_auth_router.post("/register", response_model=schemas.MobileRegisterResponse, status_code=201)
async def mobile_register(
    body: schemas.MobileRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Complete registration for a new mobile user."""
    email = body.email.strip().lower()
    mobile = body.mobile.strip()
    cleaned_mobile = clean_phone_number(mobile)

    # Check email uniqueness
    existing_email = await db.scalar(
        select(User).where(User.email == email)
    )
    if existing_email:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Check mobile uniqueness
    last_digits = cleaned_mobile[-10:]
    existing_mobile = await db.scalar(
        select(User).where((User.phone == cleaned_mobile) | (User.phone.like(f"%{last_digits}")))
    )
    if existing_mobile:
        raise HTTPException(status_code=400, detail="User with this mobile number already exists")

    # Create user profile
    new_user = User(
        email=email,
        full_name=f"{body.first_name.strip()} {body.last_name.strip()}".strip(),
        phone=cleaned_mobile,
        is_active=True,
        is_verified=True
    )
    
    # Assign student role
    student_role = await db.scalar(
        select(Role).where(Role.name == "student")
    )
    if student_role:
        new_user.roles.append(student_role)
    else:
        from app.modules.auth.services import get_or_create_role
        student_role = await get_or_create_role(db, "student")
        new_user.roles.append(student_role)

    db.add(new_user)
    await db.flush()

    # Create Student record
    new_student = Student(
        user_id=new_user.id,
        course_id=None,
        address=body.address.strip(),
        qualification=body.qualification.strip(),
        gender=body.gender.strip(),
        dob=body.dob.strip()
    )
    db.add(new_student)
    await db.commit()

    return schemas.MobileRegisterResponse(
        success=True,
        message="Registration completed",
        user_id=new_user.id
    )


# Dedicated Mobile Profile router
mobile_profile_router = APIRouter(prefix="/mobile/profile", tags=["Mobile Profile"])

@mobile_profile_router.get("", response_model=schemas.MobileProfileResponse)
async def get_mobile_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details for the currently logged in user/student profile."""
    student = await db.scalar(
        select(Student).where(Student.user_id == current_user.id)
    )

    parts = (current_user.full_name or "").split(" ", 1)
    first_name = parts[0] if len(parts) > 0 else ""
    last_name = parts[1] if len(parts) > 1 else ""

    data = schemas.MobileProfileData(
        id=current_user.id,
        first_name=first_name,
        last_name=last_name,
        email=current_user.email,
        mobile=current_user.phone,
        gender=student.gender if student else None,
        dob=student.dob if student else None,
        address=student.address if student else None,
        qualification=student.qualification if student else None
    )

    return schemas.MobileProfileResponse(
        success=True,
        data=data
    )

@mobile_profile_router.put("", response_model=schemas.MobileProfileUpdateResponse)
async def update_mobile_profile(
    body: schemas.MobileProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update profile fields for the authenticated student."""
    parts = (current_user.full_name or "").split(" ", 1)
    current_first_name = parts[0] if len(parts) > 0 else ""
    current_last_name = parts[1] if len(parts) > 1 else ""

    first_name = body.first_name.strip() if (body.first_name is not None) else current_first_name
    last_name = body.last_name.strip() if (body.last_name is not None) else current_last_name
    
    current_user.full_name = f"{first_name} {last_name}".strip()

    if body.email is not None:
        email = body.email.strip().lower()
        if email != current_user.email:
            existing = await db.scalar(
                select(User).where(User.email == email)
            )
            if existing:
                raise HTTPException(status_code=400, detail="User with this email already exists")
            current_user.email = email

    # Fetch or create student profile record
    student = await db.scalar(
        select(Student).where(Student.user_id == current_user.id)
    )
    if not student:
        student = Student(user_id=current_user.id)
        db.add(student)

    if body.address is not None:
        student.address = body.address.strip()
    if body.gender is not None:
        student.gender = body.gender.strip()
    if body.dob is not None:
        student.dob = body.dob.strip()
    if body.qualification is not None:
        student.qualification = body.qualification.strip()

    await db.commit()

    return schemas.MobileProfileUpdateResponse(
        success=True,
        message="Profile updated successfully"
    )

# --- Mobile Profile V1 Router ---
mobile_v1_router = APIRouter(prefix="/v1", tags=["Mobile Profile V1"])

@mobile_v1_router.post("/user", response_model=schemas.MobileUserProfileResponse, status_code=201)
async def create_mobile_user_profile(
    body: schemas.MobileUserProfileCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create or update a user and student profile without requiring authentication."""
    name = body.name.strip()
    email = body.email.strip().lower()
    mobile_number = body.mobileNumber.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not mobile_number:
        raise HTTPException(status_code=400, detail="Mobile number is required")

    # Find if user already exists by email
    user = await db.scalar(
        select(User).where(User.email == email)
    )

    if not user:
        # Create a new user with default 'student' role
        from app.modules.auth.services import get_or_create_role
        role = await get_or_create_role(db, "student")
        
        user = User(
            email=email,
            full_name=name,
            phone=mobile_number,
            is_active=True,
            is_verified=True
        )
        user.roles.append(role)
        db.add(user)
        await db.flush()
    else:
        # Update existing user details
        user.full_name = name
        user.phone = mobile_number

    # Sync KYCSubmission mobile if it exists
    from app.modules.kyc.models import KYCSubmission
    kyc = await db.scalar(
        select(KYCSubmission).where(KYCSubmission.user_id == user.id)
    )
    if kyc:
        kyc.mobile = mobile_number

    # Ensure Student profile exists
    student = await db.scalar(
        select(Student).where(Student.user_id == user.id)
    )
    if not student:
        student = Student(
            user_id=user.id,
            course_id=None,
            address=None,
            qualification=None,
            gender=None,
            dob=None
        )
        db.add(student)

    await db.commit()
    await db.refresh(user)

    role_names = [r.name for r in user.roles]
    primary_role = role_names[0] if role_names else "user"

    data = schemas.MobileUserProfileResponseData(
        id=str(user.id),
        name=user.full_name,
        email=user.email,
        mobileNumber=user.phone or "",
        role=primary_role
    )

    return schemas.MobileUserProfileResponse(
        success=True,
        message="User profile created successfully",
        data=data
    )

@mobile_v1_router.put("/user/{user_id}", response_model=schemas.MobileUserProfileResponse)
async def update_mobile_user_profile(
    user_id: int,
    body: schemas.MobileUserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update profile details for the authenticated user."""
    # Ensure current user is updating their own profile
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to update this profile")

    name = body.name.strip()
    email = body.email.strip().lower()
    mobile_number = body.mobileNumber.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not mobile_number:
        raise HTTPException(status_code=400, detail="Mobile number is required")

    # Ensure profile already exists (Student record must exist)
    existing_student = await db.scalar(
        select(Student).where(Student.user_id == current_user.id)
    )
    if not existing_student:
        raise HTTPException(status_code=400, detail="Profile does not exist. Please create it first.")

    # Check email uniqueness (must not be in use by another user)
    email_user = await db.scalar(
        select(User).where(User.email == email, User.id != current_user.id)
    )
    if email_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Update User model details
    current_user.full_name = name
    current_user.email = email
    current_user.phone = mobile_number

    # Sync KYCSubmission mobile if it exists
    from app.modules.kyc.models import KYCSubmission
    kyc = await db.scalar(
        select(KYCSubmission).where(KYCSubmission.user_id == current_user.id)
    )
    if kyc:
        kyc.mobile = mobile_number

    await db.commit()
    await db.refresh(current_user)

    role_names = [r.name for r in current_user.roles]
    primary_role = role_names[0] if role_names else "user"

    data = schemas.MobileUserProfileResponseData(
        id=str(current_user.id),
        name=current_user.full_name,
        email=current_user.email,
        mobileNumber=current_user.phone or "",
        role=primary_role
    )

    return schemas.MobileUserProfileResponse(
        success=True,
        message="User profile updated successfully",
        data=data
    )

@mobile_v1_router.get("/auth/me", response_model=schemas.MobileAuthMeResponse)
async def get_mobile_auth_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details for the currently logged in user/student profile."""
    # Check if student profile exists
    student = await db.scalar(
        select(Student).where(Student.user_id == current_user.id)
    )
    if not student:
        # Profile does not exist yet (but authenticated user does)
        return schemas.MobileAuthMeResponse(
            success=True,
            data=None
        )

    # Return profile data
    role_names = [r.name for r in current_user.roles]
    primary_role = role_names[0] if role_names else "user"

    data = schemas.MobileUserProfileResponseData(
        id=str(current_user.id),
        name=current_user.full_name,
        email=current_user.email,
        mobileNumber=current_user.phone or "",
        role=primary_role
    )

    return schemas.MobileAuthMeResponse(
        success=True,
        data=data
    )

