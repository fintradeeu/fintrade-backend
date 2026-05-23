"""Auth module — business logic / service layer."""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.modules.auth.models import OTPCode, Role, Session, User
from app.utils.logger import get_logger
from app.utils.smtp_notifications import (
    build_otp_email_html,
    send_email,
)

logger = get_logger(__name__)

MAX_OTP_ATTEMPTS = 5  # Lock after 5 wrong attempts


async def get_or_create_role(db: AsyncSession, role_name: str) -> Role:
    """Fetch a role by name, creating it if it doesn't exist."""
    result = await db.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        await db.flush()
    return role


async def register_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    password: str,
    phone: Optional[str] = None,
    role_name: str = "student",
) -> User:
    """Create a new user with the given role."""
    # Check uniqueness
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    role = await get_or_create_role(db, role_name)

    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(password),
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("user_registered", user_id=user.id, email=email)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verify credentials and return the user."""
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


# ── OTP helpers ──────────────────────────────────────────────────────

def _generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _generate_otp_token() -> str:
    """Generate a unique token to identify an OTP session."""
    return secrets.token_hex(32)


async def generate_and_send_otp(db: AsyncSession, user: User) -> dict:
    """Create an OTP, persist it, and send via SMS + Email.

    Returns:
        dict with otp_token, expires_in_seconds, and channels used
    """
    code = _generate_otp_code()
    otp_token = _generate_otp_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    # Store in DB
    otp = OTPCode(
        user_id=user.id,
        code=code,
        otp_token=otp_token,
        channel="email",
        expires_at=expires_at,
    )
    db.add(otp)
    await db.flush()

    # Send via email channel
    channels_sent = []

    # Email — always sent (email is mandatory in registration)
    email_html = build_otp_email_html(code, user.full_name)
    email_sent = await send_email(
        to_email=user.email,
        subject=f"{code} — Your FinTrade Verification Code",
        body_html=email_html,
    )
    if email_sent:
        channels_sent.append("email")

    if not channels_sent:
        # Email failed — log but don't block (for dev/testing)
        logger.warning("otp_delivery_failed", user_id=user.id, code=code)

    logger.info("otp_generated", user_id=user.id, channels=channels_sent)

    return {
        "otp_token": otp_token,
        "expires_in_seconds": settings.OTP_EXPIRY_MINUTES * 60,
        "channels": channels_sent,
    }


async def verify_otp(db: AsyncSession, otp_token: str, code: str) -> User:
    """Validate an OTP code and return the associated user.

    Raises HTTPException on invalid/expired/used codes.
    """
    result = await db.execute(
        select(OTPCode).where(OTPCode.otp_token == otp_token)
    )
    otp = result.scalar_one_or_none()

    if otp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification session",
        )

    if otp.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This code has already been used",
        )

    if datetime.now(timezone.utc) > otp.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one.",
        )

    if otp.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    if otp.code != code.strip():
        otp.attempts += 1
        await db.flush()
        remaining = MAX_OTP_ATTEMPTS - otp.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect code. {remaining} attempt(s) remaining.",
        )

    # Mark as used
    otp.is_used = True
    await db.flush()

    # Fetch the full user with roles
    user_result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == otp.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info("otp_verified", user_id=user.id)
    return user


async def resend_otp(db: AsyncSession, otp_token: str) -> dict:
    """Invalidate the old OTP and send a fresh one.

    Returns the same dict structure as generate_and_send_otp.
    """
    result = await db.execute(
        select(OTPCode).where(OTPCode.otp_token == otp_token)
    )
    otp = result.scalar_one_or_none()

    if otp is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification session",
        )

    # Mark old OTP as used
    otp.is_used = True
    await db.flush()

    # Fetch user
    user_result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == otp.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Generate new OTP
    return await generate_and_send_otp(db, user)


# ── Session management ───────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Issue JWT tokens and persist a session row."""
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    session = Session(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
        is_active=True,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.flush()
    logger.info("session_created", user_id=user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


async def revoke_session(db: AsyncSession, user_id: int, token: str):
    """Mark a session as inactive (logout)."""
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.token == token,
            Session.is_active == True,  # noqa: E712
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.is_active = False
        await db.flush()
        logger.info("session_revoked", user_id=user_id)
