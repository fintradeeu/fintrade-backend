"""AWS Notification Service — SNS (SMS) + SES (Email) for OTP delivery."""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_sns_client():
    """Create an SNS client for sending SMS."""
    return boto3.client(
        "sns",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _get_ses_client():
    """Create an SES client for sending emails."""
    return boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def send_sms(phone_number: str, message: str) -> bool:
    """Send an SMS message via AWS SNS.

    Args:
        phone_number: E.164 format phone number (e.g. +919558291065)
        message: Text content to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        logger.warning("aws_sms_skipped", reason="AWS credentials not configured")
        return False

    try:
        client = _get_sns_client()
        response = client.publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SenderID": {
                    "DataType": "String",
                    "StringValue": "FinTrade",
                },
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",
                },
            },
        )
        logger.info(
            "sms_sent",
            phone=phone_number[-4:],  # Log only last 4 digits
            message_id=response.get("MessageId"),
        )
        return True
    except (ClientError, NoCredentialsError) as e:
        logger.error("sms_send_failed", phone=phone_number[-4:], error=str(e))
        return False


async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Send an email via AWS SES.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body_html: HTML body content

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        logger.warning("aws_email_skipped", reason="AWS credentials not configured")
        return False

    try:
        client = _get_ses_client()
        response = client.send_email(
            Source=settings.SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": body_html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(
            "email_sent",
            to=to_email,
            message_id=response.get("MessageId"),
        )
        return True
    except (ClientError, NoCredentialsError) as e:
        logger.error("email_send_failed", to=to_email, error=str(e))
        return False


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
                <td style="background:linear-gradient(135deg,#E53935,#b71c1c);padding:32px 24px;text-align:center;">
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
                    <div style="background:#f8f8f8;border:2px dashed #E53935;border-radius:8px;padding:20px;text-align:center;margin:0 0 24px;">
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


def build_otp_sms_message(otp_code: str) -> str:
    """Build the SMS message text for OTP delivery."""
    return f"{otp_code} is your FinTrade verification code. Valid for {settings.OTP_EXPIRY_MINUTES} min. Do not share this code."
