"""Lectures module — service layer."""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import selectinload

from app.modules.lectures.models import Lecture, LectureRecording, RegistrationOTP
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_lecture(db: AsyncSession, data: dict) -> Lecture:
    """Admin/faculty creates a scheduled lecture."""
    lecture = Lecture(
        title=data["title"],
        description=data.get("description"),
        course_id=data["course_id"],
        instructor_id=data.get("instructor_id"),
        meeting_link=data.get("meeting_link"),
        scheduled_at=data["scheduled_at"],
        duration_minutes=data.get("duration_minutes", 60),
        max_participants=data.get("max_participants", 0),
    )
    db.add(lecture)
    await db.commit()
    
    # Reload with relationships
    query = select(Lecture).options(selectinload(Lecture.recordings)).filter(Lecture.id == lecture.id)
    result = await db.execute(query)
    lecture = result.scalar_one()
    
    logger.info("lecture_created", lecture_id=lecture.id, title=lecture.title)
    return lecture


async def list_lectures(
    db: AsyncSession, course_id: int | None = None, skip: int = 0, limit: int = 20
) -> List[Lecture]:
    """List lectures, optionally filtered by course."""
    query = (
        select(Lecture)
        .options(selectinload(Lecture.recordings))
        .offset(skip)
        .limit(limit)
        .order_by(Lecture.scheduled_at.desc())
    )
    if course_id:
        query = query.where(Lecture.course_id == course_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def join_lecture(db: AsyncSession, user_id: int, lecture_id: int) -> dict:
    """Student joins a lecture and gets the meeting link."""
    lecture = await db.get(Lecture, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    if not lecture.meeting_link:
        raise HTTPException(status_code=400, detail="Meeting link not yet available")

    logger.info("lecture_joined", user_id=user_id, lecture_id=lecture_id)
    return {
        "lecture_id": lecture.id,
        "meeting_link": lecture.meeting_link,
        "message": f"Joined lecture: {lecture.title}",
    }


async def start_lecture(db: AsyncSession, lecture_id: int) -> Lecture:
    """Start a lecture (set is_live=True)."""
    result = await db.execute(select(Lecture).options(selectinload(Lecture.recordings)).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    
    lecture.is_live = True
    lecture.is_completed = False
    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_started", lecture_id=lecture.id)
    return lecture


async def end_lecture(db: AsyncSession, lecture_id: int) -> Lecture:
    """End a lecture (set is_live=False, is_completed=True)."""
    result = await db.execute(select(Lecture).options(selectinload(Lecture.recordings)).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    
    lecture.is_live = False
    lecture.is_completed = True
    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_ended", lecture_id=lecture.id)
    return lecture


async def add_recording(db: AsyncSession, lecture_id: int, recording_url: str) -> LectureRecording:
    """Add a recording to a completed lecture."""
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
        
    recording = LectureRecording(
        lecture_id=lecture.id,
        recording_url=recording_url,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    logger.info("lecture_recording_added", lecture_id=lecture.id, recording_id=recording.id)
    return recording

async def register_for_lecture(db: AsyncSession, data: dict, user_id: int | None = None) -> dict:
    from app.modules.lectures.models import LectureRegistration
    
    # Try to resolve lecture title if lecture_id is passed and title is missing
    lecture_title = data.get("lecture_title")
    lecture_id = data.get("lecture_id")
    if lecture_id and not lecture_title:
        lecture = await db.get(Lecture, lecture_id)
        if lecture:
            lecture_title = lecture.title
            
    registration = LectureRegistration(
        lecture_id=lecture_id,
        lecture_title=lecture_title,
        full_name=data["full_name"],
        email=data["email"],
        mobile_no=data["mobile_no"],
        city=data.get("city"),
        user_id=user_id
    )
    db.add(registration)
    await db.commit()
    await db.refresh(registration)
    logger.info("lecture_registration_created", reg_id=registration.id, email=registration.email)
    return registration

async def get_all_lecture_registrations(db: AsyncSession) -> List[dict]:
    from app.modules.lectures.models import LectureRegistration
    query = select(LectureRegistration).order_by(LectureRegistration.registered_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def send_registration_otp(db: AsyncSession, email: str, lecture_title: str | None) -> None:
    from app.modules.lectures.models import LectureRegistration, RegistrationOTP
    from app.utils.smtp_notifications import send_email
    
    # Normalize email
    normalized_email = email.strip().lower()
    
    # Check if already registered
    if lecture_title:
        q = select(LectureRegistration).where(
            LectureRegistration.email == normalized_email,
            LectureRegistration.lecture_title == lecture_title
        )
        existing = await db.execute(q)
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="You are already registered.")
            
    # Generate 6-digit OTP
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    # Save to db
    otp_record = RegistrationOTP(
        email=normalized_email,
        code=code,
        expires_at=expires_at,
        is_verified=False
    )
    db.add(otp_record)
    await db.commit()
    
    # Send email
    subject = f"{code} — FinTrade Registration Verification Code"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; padding: 20px;">
        <h2 style="color: #D50032; text-align: center;">FinTrade Academy</h2>
        <p>Hello,</p>
        <p>Thank you for your interest in registering for the live class: <strong>{lecture_title or 'Live Class'}</strong>.</p>
        <p>Please use the following OTP (One-Time Password) to verify your email address and complete your registration:</p>
        <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; color: #121212; background-color: #f7f7f7; border: 2px dashed #D50032; padding: 10px 20px; letter-spacing: 5px; border-radius: 5px;">{code}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code is valid for 10 minutes. Please do not share it with anyone.</p>
        <hr style="border: 0; border-top: 1px solid #eee;" />
        <p style="color: #999; font-size: 12px; text-align: center;">&copy; 2026 FinTrade. All rights reserved.</p>
    </div>
    """
    await send_email(to_email=normalized_email, subject=subject, body_html=body_html)


async def register_for_lecture_with_otp(db: AsyncSession, data: dict, user_id: int | None = None) -> Any:
    from app.modules.lectures.models import LectureRegistration, RegistrationOTP
    from app.utils.smtp_notifications import send_email
    
    email = data["email"].strip().lower()
    lecture_title = data.get("lecture_title")
    lecture_id = data.get("lecture_id")
    otp_code = data["otp"].strip()
    
    # 1. Check duplicate registration
    if lecture_title:
        q = select(LectureRegistration).where(
            LectureRegistration.email == email,
            LectureRegistration.lecture_title == lecture_title
        )
        existing = await db.execute(q)
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="You are already registered.")
            
    # 2. Verify OTP
    otp_q = select(RegistrationOTP).where(
        RegistrationOTP.email == email,
        RegistrationOTP.is_verified == False
    ).order_by(RegistrationOTP.created_at.desc())
    otp_res = await db.execute(otp_q)
    latest_otp = otp_res.scalars().first()
    
    if not latest_otp:
        raise HTTPException(status_code=400, detail="No OTP verification requested for this email.")
        
    if latest_otp.code != otp_code:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
        
    if datetime.now(timezone.utc) > latest_otp.expires_at:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
        
    # Mark OTP as verified
    latest_otp.is_verified = True
    
    # Try to resolve lecture title if lecture_id is passed and title is missing
    if lecture_id and not lecture_title:
        lecture = await db.get(Lecture, lecture_id)
        if lecture:
            lecture_title = lecture.title
            
    # 3. Create registration
    registration = LectureRegistration(
        lecture_id=lecture_id,
        lecture_title=lecture_title,
        full_name=data["full_name"],
        email=email,
        mobile_no=data["mobile_no"],
        city=data.get("city"),
        user_id=user_id
    )
    db.add(registration)
    await db.flush()
    
    # 4. Fetch the lecture link from PlatformSettings if config contains it
    from app.modules.settings.services import get_landing_page_config
    landing_config = await get_landing_page_config(db)
    live_classes = landing_config.get("live_classes", [])
    lecture_link = None
    for lc in live_classes:
        if lc.get("title") == lecture_title:
            lecture_link = lc.get("lecture_link")
            break
            
    # Send confirmation email
    confirm_subject = f"Registration Confirmed: {lecture_title or 'Live Class'}"
    confirm_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; padding: 20px;">
        <h2 style="color: #D50032; text-align: center;">Registration Successful!</h2>
        <p>Hello <strong>{data["full_name"]}</strong>,</p>
        <p>You have successfully registered for the live class: <strong>{lecture_title or 'Live Class'}</strong>.</p>
    """
    if lecture_link:
        confirm_body += f"""
        <p>Below is your exclusive link to join the lecture:</p>
        <div style="text-align: center; margin: 25px 0;">
            <a href="{lecture_link}" style="background-color: #D50032; color: white; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 5px; display: inline-block;">Join Live Class</a>
        </div>
        <p style="word-break: break-all; font-size: 13px; color: #555;">If the button doesn't work, copy and paste this link in your browser:<br/><a href="{lecture_link}">{lecture_link}</a></p>
        """
    else:
        confirm_body += f"""
        <p>The lecture link will be sent to your email address shortly before the class starts.</p>
        """
        
    confirm_body += f"""
        <p style="margin-top: 20px;">Best regards,<br/>The FinTrade Team</p>
        <hr style="border: 0; border-top: 1px solid #eee;" />
        <p style="color: #999; font-size: 12px; text-align: center;">&copy; 2026 FinTrade. All rights reserved.</p>
    </div>
    """
    
    await send_email(to_email=email, subject=confirm_subject, body_html=confirm_body)
    await db.commit()
    await db.refresh(registration)
    return registration

