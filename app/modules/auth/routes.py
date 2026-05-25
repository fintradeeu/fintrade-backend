"""Auth module — API routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union

from app.core.security import get_current_user, oauth2_scheme
from app.db.database import get_db
from app.modules.auth import schemas, services
from app.modules.auth.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=201)
async def register(
    body: schemas.RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new student account and return JWT tokens."""
    user = await services.register_user(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        phone=body.phone,
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
        phone=body.phone,
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


@router.post("/login", response_model=Union[schemas.TokenResponse, schemas.OTPPendingResponse])
async def login(
    body: schemas.LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Step 1 - Validate credentials and send OTP via email. (Admins bypass OTP)"""
    user = await services.authenticate_user(db, body.email, body.password)
    
    # Check if user has admin or super_admin role
    is_admin = False
    for role in user.roles:
        if role.name in ["admin", "super_admin"]:
            is_admin = True
            break
            
    if is_admin:
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
    otp_result = await services.generate_and_send_otp(db, user)
    
    return schemas.OTPPendingResponse(
        message="Verification code sent to your email.",
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
    return schemas.OTPPendingResponse(
        message="Verification code sent to your email for password reset.",
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
