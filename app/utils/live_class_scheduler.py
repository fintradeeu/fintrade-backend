import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.modules.lectures.models import Lecture, LectureRegistration
from app.modules.settings.services import get_landing_page_config
from app.utils.smtp_notifications import send_email
from app.utils.logger import get_logger

logger = get_logger(__name__)

def parse_scheduled_at(val: str) -> datetime | None:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            # Naive datetime: assume it is in Indian Standard Time (UTC+5:30)
            dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        return dt
    except Exception:
        return None

async def send_one_hour_notification(registration: LectureRegistration, lecture_title: str, scheduled_at: datetime, meeting_link: str):
    """Send a rich email with the Join Live Class button 1 hour before the class."""
    subject = f"⏰ Starting Soon: {lecture_title} — FinTrade Academy"
    
    formatted_time = scheduled_at.strftime("%I:%M %p")
    
    body_html = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:560px;margin:0 auto;
                background:#fff;border:1px solid #f0f0f0;border-radius:12px;overflow:hidden;">

      <!-- Header -->
      <div style="background:linear-gradient(135deg,#D50032 0%,#8B0000 100%);padding:28px 24px;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;font-weight:800;letter-spacing:0.5px;">
          FinTrade Academy
        </h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">
          Your Live Class starts in less than an hour!
        </p>
      </div>

      <!-- Body -->
      <div style="padding:28px 28px 8px;">
        <p style="font-size:15px;color:#111;margin:0 0 6px;">Hello <strong>{registration.full_name}</strong>,</p>
        <p style="font-size:14px;color:#555;margin:0 0 20px;line-height:1.6;">
          This is a reminder that the live class <strong>{lecture_title}</strong> is starting soon at <strong>{formatted_time}</strong>.
        </p>

        <!-- Meeting Link / CTA -->
        <div style="text-align:center;margin:30px 0;">
          <a href="{meeting_link}"
             style="background-color:#D50032;color:#fff;padding:14px 32px;
                    text-decoration:none;font-weight:700;font-size:16px;
                    border-radius:8px;display:inline-block;letter-spacing:0.5px;
                    box-shadow: 0 4px 10px rgba(213,0,50,0.2);">
            🎥 Join Live Class
          </a>
        </div>
        <p style="text-align:center;font-size:12px;color:#888;word-break:break-all;">
          If the button doesn't work, copy this link to your browser:<br/>
          <a href="{meeting_link}" style="color:#D50032;">{meeting_link}</a>
        </p>
      </div>

      <!-- Footer -->
      <div style="padding:16px 28px 24px;border-top:1px solid #f0f0f0;margin-top:10px;">
        <p style="font-size:13px;color:#555;margin:0 0 4px;">
          Best regards,<br/><strong>The FinTrade Team</strong>
        </p>
        <p style="font-size:11px;color:#bbb;margin:12px 0 0;text-align:center;">
          &copy; 2026 FinTrade. All rights reserved.
        </p>
      </div>
    </div>
    """
    await send_email(to_email=registration.email, subject=subject, body_html=body_html)

async def check_and_send_scheduled_emails(db):
    # Fetch all registrations where one_hour_email_sent is False
    q = select(LectureRegistration).where(LectureRegistration.one_hour_email_sent == False)
    res = await db.execute(q)
    registrations = res.scalars().all()
    
    if not registrations:
        return
        
    landing_config = None
    
    for reg in registrations:
        scheduled_at = None
        meeting_link = None
        lecture_title = reg.lecture_title
        
        # 1. Try to resolve via Lecture ID
        if reg.lecture_id:
            lecture = await db.get(Lecture, reg.lecture_id)
            if lecture:
                scheduled_at = lecture.scheduled_at
                meeting_link = lecture.meeting_link
                lecture_title = lecture.title
                
        # 2. Try to resolve via CMS config if not resolved
        if not scheduled_at or not meeting_link:
            if landing_config is None:
                landing_config = await get_landing_page_config(db)
            
            live_classes = landing_config.get("live_classes", [])
            norm_title = (reg.lecture_title or "").strip().lower()
            
            matched_class = None
            for lc in live_classes:
                lc_title = (lc.get("title") or "").strip().lower()
                if lc_title and lc_title == norm_title:
                    matched_class = lc
                    break
                    
            if matched_class:
                scheduled_at = parse_scheduled_at(matched_class.get("scheduled_at"))
                meeting_link = matched_class.get("lecture_link")
                lecture_title = matched_class.get("title")
                
        # 3. Check if time is within 1 hour
        if scheduled_at and meeting_link:
            now_utc = datetime.now(timezone.utc)
            scheduled_utc = scheduled_at.astimezone(timezone.utc)
            time_diff = scheduled_utc - now_utc
            
            # Send if it starts within next 60 minutes, and not started more than 30 minutes ago
            if timedelta(minutes=-30) <= time_diff <= timedelta(minutes=60):
                try:
                    logger.info(
                        f"sending_one_hour_live_class_email: reg_id={reg.id}, email={reg.email}, lecture={lecture_title}"
                    )
                    await send_one_hour_notification(reg, lecture_title, scheduled_at, meeting_link)
                    reg.one_hour_email_sent = True
                    await db.flush()
                except Exception as e:
                    logger.error(f"failed_sending_one_hour_live_class_email: reg_id={reg.id}, error={str(e)}")

    await db.flush()

async def live_class_scheduler_loop():
    logger.info("Starting live class notification loop...")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await check_and_send_scheduled_emails(session)
                await session.commit()
        except Exception as e:
            logger.error(f"error_in_live_class_scheduler_loop: {str(e)}")
        # Wait 60 seconds
        await asyncio.sleep(60)
