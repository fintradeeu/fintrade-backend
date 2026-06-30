"""SMTP Notification Service — Email delivery for OTP."""

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.utils.logger import get_logger
from fastapi.concurrency import run_in_threadpool

logger = get_logger(__name__)

def _send_email_sync(to_email: str, subject: str, body_html: str) -> bool:
    """Synchronous function to send email via SMTP SSL."""
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg.set_content("Please enable HTML to view this email.")
        msg.add_alternative(body_html, subtype="html")

        logger.info("smtp_connecting", host=settings.SMTP_HOST, port=settings.SMTP_PORT)
        
        if settings.SMTP_PORT == 587:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            # Fallback to SMTP_SSL for port 465 or others
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

        logger.info("email_sent", to=to_email, subject=subject)
        return True
    except Exception as e:
        logger.error("email_send_failed", to=to_email, error=str(e))
        return False

async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Asynchronously send an email using run_in_threadpool."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("smtp_email_skipped", reason="SMTP credentials not configured")
        return False

    return await run_in_threadpool(_send_email_sync, to_email, subject, body_html)

def build_otp_email_html(otp_code: str, user_name: str) -> str:
    """Build a branded HTML email for OTP delivery."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:40px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <!-- Header -->
            <tr>
                <td style="background:linear-gradient(135deg,#0B2A5B,#1a3d7a);padding:32px 24px;text-align:center;">
                    <h1 style="color:#ffffff;font-size:24px;margin:0;">FinTrade</h1>
                    <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:8px 0 0;">Verification Code</p>
                </td>
            </tr>
            <!-- Body -->
            <tr>
                <td style="padding:32px 24px;">
                    <p style="color:#333;font-size:16px;margin:0 0 8px;">Hello {user_name},</p>
                    <p style="color:#666;font-size:14px;line-height:1.6;margin:0 0 24px;">
                        Use the following code to complete your sign-in. This code is valid for {settings.OTP_EXPIRY_MINUTES} minutes.
                    </p>
                    <!-- OTP Code -->
                    <div style="background:#f8f8f8;border:2px dashed #0B2A5B;border-radius:8px;padding:20px;text-align:center;margin:0 0 24px;">
                        <span style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#121212;">{otp_code}</span>
                    </div>
                    <p style="color:#999;font-size:12px;line-height:1.5;margin:0;">
                        If you didn't request this code, please ignore this email. Never share this code with anyone.
                    </p>
                </td>
            </tr>
            <!-- Footer -->
            <tr>
                <td style="background:#f8f8f8;padding:16px 24px;text-align:center;border-top:1px solid #eee;">
                    <p style="color:#999;font-size:12px;margin:0;">&copy; 2026 FinTrade. All rights reserved.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

def build_ib_registration_email_html(email: str, password: str, user_name: str, referral_code: str) -> str:
    """Build a branded HTML email for IB self-registration credentials."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:40px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
            <!-- Header -->
            <tr>
                <td style="background:linear-gradient(135deg,#0B2A5B,#1a3d7a);padding:32px 24px;text-align:center;">
                    <h1 style="color:#ffffff;font-size:24px;margin:0;">FinTrade</h1>
                    <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:8px 0 0;">Introducing Broker Registration</p>
                </td>
            </tr>
            <!-- Body -->
            <tr>
                <td style="padding:32px 24px;">
                    <p style="color:#333;font-size:16px;margin:0 0 8px;font-weight:bold;">Hello {user_name},</p>
                    <p style="color:#666;font-size:14px;line-height:1.6;margin:0 0 24px;">
                        Thank you for registering as an Introducing Broker (IB) with FinTrade! Your application has been submitted and is currently pending review by our administrator.
                    </p>
                    
                    <p style="color:#333;font-size:14px;font-weight:bold;margin:0 0 12px;">Your Account Credentials:</p>
                    <div style="background:#f8f8f8;border:1px solid #ddd;border-radius:8px;padding:16px;margin:0 0 24px;font-family:monospace;font-size:14px;color:#333;">
                        <div style="margin-bottom:8px;"><strong>Login Email (ID):</strong> {email}</div>
                        <div><strong>Password:</strong> {password}</div>
                    </div>

                    <p style="color:#333;font-size:14px;font-weight:bold;margin:0 0 12px;">Your Referral Details:</p>
                    <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:16px;margin:0 0 24px;text-align:center;">
                        <span style="font-size:14px;color:#666;display:block;margin-bottom:4px;">Referral Code</span>
                        <span style="font-size:20px;font-weight:bold;color:#ff8f00;letter-spacing:1px;">{referral_code}</span>
                    </div>

                    <p style="color:#666;font-size:14px;line-height:1.6;margin:0 0 24px;">
                        Once the administrator approves your KYC documents and details, you will be able to log in to your dashboard and start referring students.
                    </p>
                    
                    <p style="color:#999;font-size:12px;line-height:1.5;margin:0;border-top:1px solid #eee;padding-top:16px;">
                        If you did not initiate this registration, please contact our support team immediately.
                    </p>
                </td>
            </tr>
            <!-- Footer -->
            <tr>
                <td style="background:#f8f8f8;padding:16px 24px;text-align:center;border-top:1px solid #eee;">
                    <p style="color:#999;font-size:12px;margin:0;">&copy; 2026 FinTrade. All rights reserved.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
