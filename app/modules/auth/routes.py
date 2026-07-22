"""Auth module — API routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from app.core.security import get_current_user, oauth2_scheme, require_roles
from app.db.database import get_db
from app.modules.auth import schemas, services
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Union[schemas.TokenResponse, schemas.OTPPendingResponse], status_code=201)
async def register(
    body: schemas.RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new student account and return OTP pending response.""" 
    user = await services.register_user(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        phone=body.phone,
        city=body.city,
        referral_code=body.referral_code,
    )   
    
    channel = "both" if user.phone else "email"
    otp_result = await services.generate_and_send_otp(db, user, channel=channel)
    
    sent_channels = otp_result.get("channels", [])
    if "sms" in sent_channels and "email" in sent_channels:
        message_text = "Verification code sent to your email and mobile number via SMS."
    elif "sms" in sent_channels:
        message_text = "Verification code sent to your mobile number via SMS."
    else:
        message_text = "Verification code sent to your email."
        
    await db.commit()
    
    return schemas.OTPPendingResponse(
        message=message_text,
        otp_token=otp_result["otp_token"],
        expires_in_seconds=otp_result["expires_in_seconds"],
        channels=otp_result["channels"],
    )


@router.post("/google", response_model=schemas.TokenResponse)
async def google_auth(
    body: schemas.GoogleAuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate or register via Google OAuth ID token."""
    user = await services.authenticate_or_register_google_user(
        db,
        token=body.token,
        access_token=body.access_token,
        phone=body.phone,
        city=body.city,
    )
    tokens = await services.create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return schemas.TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=schemas.UserResponse.model_validate(user),
    )


@router.post("/google/complete-profile", response_model=schemas.UserResponse)
async def complete_google_profile(
    body: schemas.GoogleProfileCompletionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete mobile and password setup after Google sign-in."""
    user = await services.complete_google_profile(
        db,
        current_user,
        phone=body.phone,
        city=body.city,
        password=body.password,
    )
    return schemas.UserResponse.model_validate(user)


@router.post("/login", response_model=Union[schemas.TokenResponse, schemas.OTPPendingResponse])
async def login(
    body: schemas.LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Step 1 - Validate credentials and send OTP via email. (Admins bypass OTP)"""
    user = await services.authenticate_user(db, body.email, body.password)
    
    # Admin and Super Admin bypass OTP. IB/distributor accounts must verify by email OTP.
    user_role_names = {role.name for role in user.roles}
    is_otp_bypassed = False
    for role in user.roles:
        if role.name in ["admin", "super_admin"]:
            is_otp_bypassed = True
            break
            
    if is_otp_bypassed:
        # Bypass OTP, generate session immediately
        tokens = await services.create_session(
            db,
            user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return schemas.TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=schemas.UserResponse.model_validate(user),
        )
    
    # Normal user flow: Generate OTP
    is_phone = services._looks_like_phone(body.email)
    channel = "sms" if is_phone else "email"
    otp_result = await services.generate_and_send_otp(db, user, channel=channel)
    
    message_text = "Verification code sent to your email."
    if "sms" in otp_result.get("channels", []):
        message_text = "Verification code sent to your mobile number via SMS."
        
    return schemas.OTPPendingResponse(
        message=message_text,
        otp_token=otp_result["otp_token"],
        expires_in_seconds=otp_result["expires_in_seconds"],
        channels=otp_result["channels"],
    )


@router.post("/verify-otp", response_model=schemas.TokenResponse)
async def verify_otp(
    body: schemas.OTPVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Step 2 — Verify OTP code and return JWT tokens."""
    user = await services.verify_otp(db, body.otp_token, body.code)
    tokens = await services.create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return schemas.TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=schemas.UserResponse.model_validate(user),
    )
# ffffff

@router.post("/resend-otp", response_model=schemas.OTPPendingResponse)
async def resend_otp(
    body: schemas.OTPResendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend a new OTP code (invalidates the previous one)."""
    otp_result = await services.resend_otp(db, body.otp_token)
    return schemas.OTPPendingResponse(
        message="New verification code sent",
        otp_token=otp_result["otp_token"],
        expires_in_seconds=otp_result["expires_in_seconds"],
        channels=otp_result["channels"],
    )



@router.post("/cancel-registration", response_model=schemas.MessageResponse)
async def cancel_registration(
    body: schemas.OTPCancelRequest,
    db: AsyncSession = Depends(get_db),
):
    """Cancel an unverified registration and delete the associated user."""
    await services.cancel_registration(db, body.otp_token)
    return schemas.MessageResponse(message="Registration cancelled successfully")


@router.get("/me", response_model=schemas.UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return schemas.UserResponse.model_validate(current_user)


@router.get("/my-profile", response_model=schemas.UserResponse)
async def my_profile(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return schemas.UserResponse.model_validate(current_user)


@router.put("/me", response_model=schemas.UserResponse)
async def update_me(
    body: schemas.ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the currently authenticated user's profile."""
    user = await services.update_user_profile(
        db,
        current_user,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        city=body.city,
    )
    return schemas.UserResponse.model_validate(user)


@router.put("/my-profile", response_model=schemas.UserResponse)
async def update_my_profile(
    body: schemas.ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the currently authenticated user's profile."""
    user = await services.update_user_profile(
        db,
        current_user,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        city=body.city,
    )
    return schemas.UserResponse.model_validate(user)


@router.post("/me", response_model=schemas.UserResponse)
async def update_me_post(
    body: schemas.ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile. Kept for clients/proxies that reject PUT."""
    user = await services.update_user_profile(
        db,
        current_user,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        city=body.city,
    )
    return schemas.UserResponse.model_validate(user)


@router.post("/my-profile", response_model=schemas.UserResponse)
async def update_my_profile_post(
    body: schemas.ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile. Kept for clients/proxies that reject PUT."""
    user = await services.update_user_profile(
        db,
        current_user,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        city=body.city,
    )
    return schemas.UserResponse.model_validate(user)


@router.post("/logout", response_model=schemas.MessageResponse)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current session."""
    await services.revoke_session(db, current_user.id, token)
    return schemas.MessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=schemas.OTPPendingResponse)
async def forgot_password(
    body: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 1 - Send password reset OTP to email."""
    otp_result = await services.initiate_forgot_password(db, body.email)
    message_text = "Verification code sent to your email for password reset."
    if "sms" in otp_result.get("channels", []):
        message_text = "Verification code sent to your mobile number via SMS for password reset."
        
    return schemas.OTPPendingResponse(
        message=message_text,
        otp_token=otp_result["otp_token"],
        expires_in_seconds=otp_result["expires_in_seconds"],
        channels=otp_result["channels"],
    )


@router.post("/reset-password", response_model=schemas.MessageResponse)
async def reset_password(
    body: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 2 - Verify OTP and update user's password."""
    return await services.complete_reset_password(
        db,
        otp_token=body.otp_token,
        code=body.code,
        new_password=body.new_password,
    )


@router.post("/cookie-consent", response_model=schemas.CookieConsentResponse, status_code=201)
async def create_cookie_consent(
    body: schemas.CookieConsentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Log a cookie policy view/consent from a user or visitor."""
    user = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            user_id = int(payload.get("sub"))
            user = await db.get(User, user_id)
        except Exception:
            pass

    from app.modules.auth.models import CookieConsent
    consent = CookieConsent(
        user_id=user.id if user else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        consent_type=body.consent_type,
    )
    db.add(consent)
    await db.commit()
    await db.refresh(consent)
    if user:
        consent.user = user
    return consent


from typing import List

@router.get("/cookie-consents", response_model=List[schemas.CookieConsentResponse])
async def list_cookie_consents(
    current_user: User = Depends(require_roles(["super_admin", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all logged cookie policy consents for the admin panel."""
    from app.modules.auth.models import CookieConsent
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(CookieConsent)
        .options(selectinload(CookieConsent.user).selectinload(User.roles))
        .order_by(CookieConsent.created_at.desc())
    )
    return result.scalars().all()
