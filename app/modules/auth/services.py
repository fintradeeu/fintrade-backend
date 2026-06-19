"""Auth module — business logic / service layer."""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, desc
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

import httpx

logger = get_logger(__name__)

MAX_OTP_ATTEMPTS = 5  # Lock after 5 wrong attempts


def _looks_like_phone(identifier: str) -> bool:
    digits = "".join(c for c in identifier if c.isdigit())
    return len(digits) >= 8


def _phone_login_variants(identifier: str) -> list[str]:
    """Possible stored forms for the same Indian mobile number."""
    stripped = identifier.strip()
    digits = "".join(c for c in stripped if c.isdigit())
    variants = {stripped, digits}
    if len(digits) >= 10:
        last_digits = digits[-10:]
        variants.update(
            {
                last_digits,
                f"91{last_digits}",
                f"+91{last_digits}",
                f"+{digits}",
            }
        )
    return [variant for variant in variants if variant]


async def _get_login_candidates(db: AsyncSession, identifier: str) -> list[User]:
    """Return possible users for an email or phone login without assuming uniqueness."""
    identifier = identifier.strip()
    if _looks_like_phone(identifier):
        digits = "".join(c for c in identifier if c.isdigit())
        last_digits = digits[-10:]

        exact_result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.phone.in_(_phone_login_variants(identifier)))
            .order_by(desc(User.id))
        )
        exact_candidates = list(exact_result.scalars().all())
        if exact_candidates:
            return exact_candidates

        result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.phone.like(f"%{last_digits}"))
            .order_by(desc(User.id))
        )
    else:
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == identifier)
            .order_by(desc(User.id))
        )
    return list(result.scalars().all())


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
    city: Optional[str] = None,
    role_name: str = "student",
    referral_code: Optional[str] = None,
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
        city=city,
        hashed_password=hash_password(password),
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("user_registered", user_id=user.id, email=email)

    if referral_code:
        from app.modules.distributors.models import Distributor, StudentReferral
        dist_res = await db.execute(
            select(Distributor).where(Distributor.referral_code == referral_code)
        )
        distributor = dist_res.scalar_one_or_none()
        if distributor:
            referral = StudentReferral(
                student_id=user.id,
                distributor_id=distributor.id,
                course_id=None,
            )
            db.add(referral)
            await db.flush()
            logger.info("user_referred_by_distributor", user_id=user.id, distributor_id=distributor.id)

    return user


async def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return user info."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": token},
            timeout=10.0,
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )
    data = resp.json()
    # Verify the token was issued for our app
    allowed_client_ids = [cid.strip() for cid in settings.GOOGLE_CLIENT_ID.split(",") if cid.strip()]
    if data.get("aud") not in allowed_client_ids:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token audience",
        )
    if data.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token issuer",
        )
    return data


def _extract_google_city(google_people_data: dict) -> Optional[str]:
    """Best-effort extraction of a city from Google People API data."""
    for address in google_people_data.get("addresses", []) or []:
        city = address.get("city") or address.get("locality")
        if city:
            return city.strip()

        formatted = address.get("formattedValue")
        if formatted:
            parts = [part.strip() for part in formatted.split(",") if part.strip()]
            if parts:
                return parts[-2] if len(parts) >= 2 else parts[-1]

    for location in google_people_data.get("locations", []) or []:
        value = location.get("value")
        if value:
            return value.strip()

    return None


async def _fetch_google_profile_from_access_token(access_token: str) -> dict:
    """Fetch verified Google profile data using an OAuth access token."""
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers=headers,
            timeout=10.0,
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google access token",
            )
        userinfo = userinfo_resp.json()

        people_resp = await client.get(
            "https://people.googleapis.com/v1/people/me",
            params={
                "personFields": "names,emailAddresses,phoneNumbers,addresses,locations,photos",
                "sources": "READ_SOURCE_TYPE_PROFILE",
            },
            headers=headers,
            timeout=10.0,
        )

    people_data = people_resp.json() if people_resp.status_code == 200 else {}

    email = userinfo.get("email")
    if not email:
        for email_entry in people_data.get("emailAddresses", []) or []:
            email = email_entry.get("value")
            if email:
                break

    name = userinfo.get("name")
    if not name:
        for name_entry in people_data.get("names", []) or []:
            name = name_entry.get("displayName")
            if name:
                break

    picture = userinfo.get("picture")
    if not picture:
        for photo in people_data.get("photos", []) or []:
            picture = photo.get("url")
            if picture:
                break

    phone = None
    for phone_entry in people_data.get("phoneNumbers", []) or []:
        phone = phone_entry.get("value")
        if phone:
            break

    city = _extract_google_city(people_data)

    return {
        "sub": userinfo.get("sub"),
        "email": email,
        "name": name,
        "picture": picture,
        "phone": phone,
        "city": city,
    }


async def authenticate_or_register_google_user(
    db: AsyncSession,
    token: Optional[str] = None,
    access_token: Optional[str] = None,
    phone: Optional[str] = None,
    city: Optional[str] = None,
) -> User:
    """Verify Google token and either login existing user or register a new one."""
    if access_token:
        google_data = await _fetch_google_profile_from_access_token(access_token)
    elif token:
        google_data = await verify_google_token(token)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token is required",
        )

    google_id = google_data.get("sub")
    email = google_data.get("email")
    full_name = google_data.get("name") or (email.split("@")[0] if email else "Google User")
    avatar_url = google_data.get("picture")
    phone = phone or google_data.get("phone")
    city = city or google_data.get("city")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token missing required fields",
        )

    # 1. Try to find user by google_id
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.google_id == google_id)
    )
    user = result.scalar_one_or_none()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )
        changed = False
        if phone and not user.phone:
            user.phone = phone.strip()
            changed = True
        if city and not user.city:
            user.city = city.strip()
            changed = True
        # Update avatar if changed
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            changed = True
        if changed:
            await db.flush()
        return user

    # 2. Try to find user by email (link Google to existing account)
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if user:
        user.google_id = google_id
        if avatar_url:
            user.avatar_url = avatar_url
        if phone and not user.phone:
            user.phone = phone.strip()
        if city and not user.city:
            user.city = city.strip()
        await db.flush()
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )
        return user

    # 3. Create new user with student role
    role = await get_or_create_role(db, "student")
    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        city=city,
        google_id=google_id,
        avatar_url=avatar_url,
        is_verified=True,  # Google email is verified
    )
    user.roles.append(role)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("user_registered_google", user_id=user.id, email=email)
    return user


async def complete_google_profile(
    db: AsyncSession,
    user: User,
    phone: str,
    password: str,
    city: Optional[str] = None,
) -> User:
    """Store mobile number and password for a Google-created account."""
    phone = phone.strip()
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile number is required",
        )

    existing = await db.execute(
        select(User).where(User.phone == phone, User.id != user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This mobile number is already registered with another account",
        )

    user.phone = phone
    user.city = city.strip() if city else user.city
    user.hashed_password = hash_password(password)
    user.is_verified = True
    await db.flush()
    logger.info("google_profile_completed", user_id=user.id)
    return user


async def authenticate_user(db: AsyncSession, email_or_phone: str, password: str) -> User:
    """Verify credentials (email or phone number) and return the user."""
    identifier = email_or_phone.strip()

    candidates = await _get_login_candidates(db, identifier)
    matching_users = [
        user
        for user in candidates
        if user.hashed_password and verify_password(password, user.hashed_password)
    ]

    if not matching_users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/phone or password",
        )

    if len(matching_users) > 1:
        if _looks_like_phone(identifier):
            active_matches = [user for user in matching_users if user.is_active]
            if active_matches:
                selected_user = active_matches[0]
                logger.warning(
                    "duplicate_phone_login_resolved_to_latest_active_user",
                    selected_user_id=selected_user.id,
                    matched_user_ids=[user.id for user in matching_users],
                )
                return selected_user

        logger.error(
            "duplicate_login_identifier_with_same_password",
            identifier_type="phone" if _looks_like_phone(identifier) else "email",
            user_ids=[user.id for user in matching_users],
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple accounts match this login. Please sign in with your email address.",
        )

    user = matching_users[0]
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


# ── OTP helpers ──────────────────────────────────────────────────────

async def update_user_profile(
    db: AsyncSession,
    user: User,
    email: str,
    full_name: str,
    phone: Optional[str] = None,
    city: Optional[str] = None,
) -> User:
    """Update editable profile fields for the current user."""
    normalized_email = email.strip().lower()
    if normalized_email != user.email:
        existing = await db.execute(select(User).where(User.email == normalized_email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        user.email = normalized_email

    user.full_name = full_name.strip()
    user.phone = phone.strip() if phone else None
    if city is not None:
        user.city = city.strip()
    await db.flush()
    await db.refresh(user)
    logger.info("user_profile_updated", user_id=user.id)
    return user


def _generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _generate_otp_token() -> str:
    """Generate a unique token to identify an OTP session."""
    return secrets.token_hex(32)


async def generate_and_send_otp(db: AsyncSession, user: User, channel: Optional[str] = None) -> dict:
    """Create an OTP, persist it, and send via SMS or Email based on chosen channel.

    Returns:
        dict with otp_token, expires_in_seconds, and channels used
    """
    otp_token = _generate_otp_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    
    channels_sent = []
    
    use_sms = False
    if channel == "sms":
        use_sms = True
    elif channel == "email":
        use_sms = False
    else:
        use_sms = bool(user.phone)
        
    # Check if user has phone number for SMS OTP
    if use_sms and user.phone:
        from app.core.twilio_otp import get_sms_gateway_status, is_local_sms_otp_enabled, send_sms_otp

        logger.info("sms_gateway_status", **get_sms_gateway_status())

        if is_local_sms_otp_enabled():
            code = _generate_otp_code()
        else:
            code = "000000"  # Placeholder code in DB for Twilio Verify (code is managed by Twilio)
        
        # Store in DB
        otp = OTPCode(
            user_id=user.id,
            code=code,
            otp_token=otp_token,
            channel="sms",
            expires_at=expires_at,
        )
        db.add(otp)
        await db.flush()
        
        print(f"\n🔑 [OTP SERVICE] Generated SMS OTP code: {code} for user: {user.email}\n", flush=True)
        
        # send_sms_otp handles errors internally or bubbles up
        sms_sent = await send_sms_otp(user.phone, code)
        if sms_sent:
            channels_sent.append("sms")
        elif user.email:
            logger.warning("sms_otp_delivery_failed_falling_back_to_email", user_id=user.id)
            otp.channel = "email"
            email_html = build_otp_email_html(code, user.full_name)
            email_sent = await send_email(
                to_email=user.email,
                subject=f"{code} - Your FinTrade Verification Code",
                body_html=email_html,
            )
            if email_sent:
                channels_sent.append("email")
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to send SMS OTP. Please check the Nimbus SMS gateway response in backend logs.",
            )
    else:
        # Fallback to standard Email OTP
        code = _generate_otp_code()
        
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
        
        print(f"\n🔑 [OTP SERVICE] Generated Email OTP code: {code} for user: {user.email}\n", flush=True)
        
        email_html = build_otp_email_html(code, user.full_name)
        email_sent = await send_email(
            to_email=user.email,
            subject=f"{code} — Your FinTrade Verification Code",
            body_html=email_html,
        )
        if email_sent:
            channels_sent.append("email")

    if not channels_sent:
        logger.warning("otp_delivery_failed", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to deliver OTP. Please check SMS/email gateway configuration.",
        )

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

    # Fetch the full user with roles early to do channel-specific validation
    user_result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == otp.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Channel-specific validation
    if otp.channel == "sms":
        if not user.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No mobile number registered for SMS verification.",
            )
        
        # Verify code
        is_valid = False
        from app.core.twilio_otp import is_local_sms_otp_enabled

        if is_local_sms_otp_enabled():
            # Verify against database record for local-code SMS gateways.
            is_valid = (otp.code == code.strip())
        else:
            # Verify via Twilio Verify API
            from app.core.twilio_otp import check_twilio_otp
            is_valid = await check_twilio_otp(user.phone, code)
            
        if not is_valid:
            otp.attempts += 1
            await db.flush()
            remaining = MAX_OTP_ATTEMPTS - otp.attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incorrect SMS code. {remaining} attempt(s) remaining.",
            )
    else:
        # Standard Email validation
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


async def initiate_forgot_password(db: AsyncSession, email_or_phone: str) -> dict:
    """Validate user exists and send OTP via SMS (if phone) or Email (fallback) for password reset."""
    identifier = email_or_phone.strip()
    is_phone = _looks_like_phone(identifier)
    candidates = await _get_login_candidates(db, identifier)
    
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email/phone not found.",
        )

    if len(candidates) > 1:
        logger.error(
            "duplicate_password_reset_identifier",
            identifier_type="phone" if is_phone else "email",
            user_ids=[user.id for user in candidates],
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple accounts match this identifier. Please use your email address or contact support.",
        )

    user = candidates[0]
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
        
    channel = "sms" if is_phone else "email"
    return await generate_and_send_otp(db, user, channel=channel)


async def complete_reset_password(db: AsyncSession, otp_token: str, code: str, new_password: str) -> dict:
    """Verify OTP and update user's password."""
    # verify_otp raises HTTPException if validation fails
    user = await verify_otp(db, otp_token, code)
    
    # Update password
    user.hashed_password = hash_password(new_password)
    await db.flush()
    await db.commit()
    logger.info("password_reset_success", user_id=user.id)
    
    return {"message": "Password reset successful. You can now login with your new password."}
