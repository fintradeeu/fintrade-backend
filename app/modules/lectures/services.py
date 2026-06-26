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

from app.modules.auth.models import User
from app.modules.courses.models import Course, CourseEnrollment
from app.modules.lectures.models import Lecture, LectureRecording, RegistrationOTP
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_lecture(db: AsyncSession, data: dict) -> Lecture:
    """Admin/faculty creates a scheduled lecture."""
    meeting_link = data.get("meeting_link")
    google_event_id = None
    
    # Auto-generate Google Meet link if not provided manually
    if not meeting_link:
        from app.integrations.google_calendar_service import GoogleCalendarService
        event_id, g_meet_link = await GoogleCalendarService.create_event(
            title=data["title"],
            scheduled_at=data["scheduled_at"],
            duration_minutes=data.get("duration_minutes", 60),
            description=data.get("description")
        )
        if g_meet_link:
            meeting_link = g_meet_link
            google_event_id = event_id

    lecture = Lecture(
        title=data["title"],
        description=data.get("description"),
        course_id=data["course_id"],
        instructor_id=data.get("instructor_id"),
        meeting_link=meeting_link,
        google_event_id=google_event_id,
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


async def update_lecture(db: AsyncSession, lecture_id: int, data: dict) -> Lecture:
    """Update a scheduled lecture."""
    query = select(Lecture).options(selectinload(Lecture.recordings)).filter(Lecture.id == lecture_id)
    result = await db.execute(query)
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    old_title = lecture.title
    old_scheduled_at = lecture.scheduled_at
    old_duration = lecture.duration_minutes
    old_desc = lecture.description
    
    # Apply modifications
    for key, val in data.items():
        if hasattr(lecture, key):
            setattr(lecture, key, val)
            
    # Sync with Google Calendar if event_id is present
    if lecture.google_event_id and (
        old_title != lecture.title or
        old_scheduled_at != lecture.scheduled_at or
        old_duration != lecture.duration_minutes or
        old_desc != lecture.description
    ):
        from app.integrations.google_calendar_service import GoogleCalendarService
        success, updated_link = await GoogleCalendarService.update_event(
            event_id=lecture.google_event_id,
            title=lecture.title,
            scheduled_at=lecture.scheduled_at,
            duration_minutes=lecture.duration_minutes,
            description=lecture.description
        )
        if success and updated_link:
            lecture.meeting_link = updated_link
            
    # Auto-generate if meeting link is cleared or missing
    elif not lecture.meeting_link:
        from app.integrations.google_calendar_service import GoogleCalendarService
        event_id, g_meet_link = await GoogleCalendarService.create_event(
            title=lecture.title,
            scheduled_at=lecture.scheduled_at,
            duration_minutes=lecture.duration_minutes,
            description=lecture.description
        )
        if g_meet_link:
            lecture.meeting_link = g_meet_link
            lecture.google_event_id = event_id

    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_updated", lecture_id=lecture.id, title=lecture.title)
    return lecture


async def delete_lecture(db: AsyncSession, lecture_id: int) -> None:
    """Delete a scheduled lecture."""
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    # Clean up Google Calendar event if it exists
    if lecture.google_event_id:
        from app.integrations.google_calendar_service import GoogleCalendarService
        await GoogleCalendarService.delete_event(lecture.google_event_id)

    await db.delete(lecture)
    await db.commit()
    logger.info("lecture_deleted", lecture_id=lecture_id)


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
    
    was_completed = bool(lecture.is_completed)
    lecture.is_live = False
    lecture.is_completed = True
    await db.commit()
    await db.refresh(lecture)
    logger.info("lecture_ended", lecture_id=lecture.id)
    if not was_completed:
        await notify_enrolled_students_lecture_finished(db, lecture)
    return lecture


async def notify_enrolled_students_lecture_finished(db: AsyncSession, lecture: Lecture) -> dict:
    """Send WhatsApp completion notification to active enrolled students for this lecture course."""
    if not lecture.course_id:
        logger.info("lecture_finished_whatsapp_skipped_no_course", lecture_id=lecture.id)
        return {"sent": 0, "failed": 0, "skipped": 0}

    from app.integrations.whatsapp_service import send_lecture_finished_message

    course = await db.get(Course, lecture.course_id)
    rows = await db.execute(
        select(User)
        .join(CourseEnrollment, CourseEnrollment.user_id == User.id)
        .where(
            CourseEnrollment.course_id == lecture.course_id,
            CourseEnrollment.is_active == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
            User.phone.isnot(None),
        )
        .distinct()
    )
    students = list(rows.scalars().all())
    sent = 0
    failed = 0
    skipped = 0
    finished_at = datetime.now(timezone.utc).strftime("%d %b %Y, %I:%M %p UTC")

    for student in students:
        if not student.phone:
            skipped += 1
            continue
        ok = await send_lecture_finished_message(
            student_phone=student.phone,
            student_name=student.full_name or "Student",
            lecture_title=lecture.title,
            course_title=course.title if course else "your course",
            finished_at=finished_at,
        )
        if ok:
            sent += 1
        else:
            failed += 1

    logger.info(
        "lecture_finished_whatsapp_notifications",
        lecture_id=lecture.id,
        course_id=lecture.course_id,
        sent=sent,
        failed=failed,
        skipped=skipped,
    )
    return {"sent": sent, "failed": failed, "skipped": skipped}


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
    
    # 4. Fetch the full live class entry from PlatformSettings CMS config
    from app.modules.settings.services import get_landing_page_config
    landing_config = await get_landing_page_config(db)
    live_classes = landing_config.get("live_classes", [])
    
    # Case-insensitive/stripped title matching to avoid mismatch bugs
    norm_title = (lecture_title or "").strip().lower()
    matched_class: dict = {}
    for lc in live_classes:
        lc_title = (lc.get("title") or "").strip().lower()
        if lc_title and lc_title == norm_title:
            matched_class = lc
            break
    
    lecture_link = matched_class.get("lecture_link") or None
    
    # Fallback: if lecture_id is known, try meeting_link from the Lecture row itself
    if not lecture_link and lecture_id:
        lec_row = await db.get(Lecture, lecture_id)
        if lec_row and lec_row.meeting_link:
            lecture_link = lec_row.meeting_link
    
    logger.info(
        "lecture_registration_link_resolved",
        email=email,
        lecture_title=lecture_title,
        lecture_id=lecture_id,
        lecture_link=lecture_link,
        matched_class=matched_class,
        live_classes_count=len(live_classes),
    )

    # ── Build rich confirmation email ──────────────────────────────────
    instructor = matched_class.get("instructor") or ""
    class_date = matched_class.get("date") or ""
    class_time = matched_class.get("time") or ""
    full_name  = data["full_name"]
    user_mobile = data.get("mobile_no", "")
    user_city   = data.get("city", "")

    confirm_subject = f"✅ Registration Confirmed: {lecture_title or 'Live Class'} — FinTrade Academy"

    # Class info rows (only show non-empty values)
    class_info_rows = ""
    if instructor:
        class_info_rows += f"""
        <tr>
          <td style="padding:8px 0;color:#555;font-size:14px;font-weight:600;width:130px;">👨‍🏫 Instructor</td>
          <td style="padding:8px 0;color:#111;font-size:14px;font-weight:700;">{instructor}</td>
        </tr>"""
    if class_date:
        class_info_rows += f"""
        <tr>
          <td style="padding:8px 0;color:#555;font-size:14px;font-weight:600;">📅 Date</td>
          <td style="padding:8px 0;color:#111;font-size:14px;font-weight:700;">{class_date}</td>
        </tr>"""
    if class_time:
        class_info_rows += f"""
        <tr>
          <td style="padding:8px 0;color:#555;font-size:14px;font-weight:600;">🕙 Time</td>
          <td style="padding:8px 0;color:#111;font-size:14px;font-weight:700;">{class_time}</td>
        </tr>"""

    # Meeting link block (No direct link / join button in registration confirmation email)
    meeting_block = """
    <div style="background:#fff8f8;border:1px dashed #D50032;border-radius:8px;
                padding:16px;margin:20px 0;text-align:center;">
      <p style="color:#D50032;font-size:14px;font-weight:600;margin:0;">
        📩 The join link will be sent to your email exactly 1 hour before the class starts.
      </p>
    </div>"""

    confirm_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:560px;margin:0 auto;
                background:#fff;border:1px solid #f0f0f0;border-radius:12px;overflow:hidden;">

      <!-- Header -->
      <div style="background:linear-gradient(135deg,#D50032 0%,#8B0000 100%);padding:28px 24px;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;font-weight:800;letter-spacing:0.5px;">
          FinTrade Academy
        </h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">
          Live Class Registration Confirmed
        </p>
      </div>

      <!-- Body -->
      <div style="padding:28px 28px 8px;">
        <p style="font-size:15px;color:#111;margin:0 0 6px;">Hello <strong>{full_name}</strong>,</p>
        <p style="font-size:14px;color:#555;margin:0 0 20px;line-height:1.6;">
          You have successfully registered for our upcoming live class. Here are all the details:
        </p>

        <!-- Class Details Card -->
        <div style="background:#fafafa;border:1px solid #eee;border-radius:10px;padding:20px 20px 10px;">
          <h2 style="color:#D50032;font-size:17px;font-weight:800;margin:0 0 14px;
                     border-bottom:2px solid #D50032/20;padding-bottom:10px;">
            {lecture_title or 'Live Class'}
          </h2>
          <table style="width:100%;border-collapse:collapse;">
            {class_info_rows}
          </table>
        </div>

        <!-- Registration Details -->
        <div style="margin-top:18px;background:#f9f9f9;border-radius:8px;padding:14px 18px;">
          <p style="font-size:11px;font-weight:700;color:#aaa;text-transform:uppercase;
                    letter-spacing:1px;margin:0 0 10px;">Your Registration Details</p>
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="padding:5px 0;color:#777;font-size:13px;width:110px;">👤 Name</td>
              <td style="padding:5px 0;color:#111;font-size:13px;font-weight:600;">{full_name}</td>
            </tr>
            <tr>
              <td style="padding:5px 0;color:#777;font-size:13px;">📧 Email</td>
              <td style="padding:5px 0;color:#111;font-size:13px;font-weight:600;">{email}</td>
            </tr>
            {"<tr><td style='padding:5px 0;color:#777;font-size:13px;'>📱 Mobile</td><td style='padding:5px 0;color:#111;font-size:13px;font-weight:600;'>"+user_mobile+"</td></tr>" if user_mobile else ""}
            {"<tr><td style='padding:5px 0;color:#777;font-size:13px;'>🏙️ City</td><td style='padding:5px 0;color:#111;font-size:13px;font-weight:600;'>"+user_city+"</td></tr>" if user_city else ""}
          </table>
        </div>

        <!-- Meeting Link / CTA -->
        {meeting_block}
      </div>

      <!-- Footer -->
      <div style="padding:16px 28px 24px;border-top:1px solid #f0f0f0;margin-top:10px;">
        <p style="font-size:13px;color:#555;margin:0 0 4px;">
          Best regards,<br/><strong>The FinTrade Team</strong>
        </p>
        <p style="font-size:11px;color:#bbb;margin:12px 0 0;text-align:center;">
          &copy; 2026 FinTrade. All rights reserved.<br/>
          If you did not register for this class, please ignore this email.
        </p>
      </div>
    </div>
    """

    await send_email(to_email=email, subject=confirm_subject, body_html=confirm_body)
    await db.commit()
    await db.refresh(registration)
    return registration



