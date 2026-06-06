"""Twilio Verify API wrapper for sending and verifying SMS OTPs."""

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def clean_phone_number(phone: str) -> str:
    """Ensure phone number is in E.164 format. Default to India (+91) if missing."""
    cleaned = phone.strip()
    # Strip any spaces, dashes, or parentheses
    cleaned = "".join(c for c in cleaned if c.isdigit() or c == "+")
    
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = f"+91{cleaned}"
        else:
            cleaned = f"+{cleaned}"
            
    return cleaned


async def send_twilio_otp(phone: str) -> bool:
    """Send verification OTP using Twilio Verify API."""
    phone_clean = clean_phone_number(phone)
    
    # Check if credentials are not configured
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_SERVICE_SID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio SMS gateway is not configured on the server."
        )

    url = f"https://verify.twilio.com/v2/Services/{settings.TWILIO_SERVICE_SID}/Verifications"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "To": phone_clean,
        "Channel": "sms"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, auth=auth, data=data, timeout=10.0)
            if resp.status_code not in (200, 201):
                logger.error("twilio_send_error", status_code=resp.status_code, body=resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Twilio Verify SMS sending failed: {resp.json().get('message', resp.text)}"
                )
            logger.info("twilio_otp_sent_successfully", phone=phone_clean)
            return True
    except httpx.RequestError as e:
        logger.error("twilio_request_exception", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Twilio Verify service."
        )


async def check_twilio_otp(phone: str, code: str) -> bool:
    """Verify OTP using Twilio Verify API."""
    phone_clean = clean_phone_number(phone)
    
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_SERVICE_SID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio SMS gateway is not configured on the server."
        )

    url = f"https://verify.twilio.com/v2/Services/{settings.TWILIO_SERVICE_SID}/VerificationCheck"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "To": phone_clean,
        "Code": code
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, auth=auth, data=data, timeout=10.0)
            if resp.status_code not in (200, 201):
                logger.error("twilio_check_error", status_code=resp.status_code, body=resp.text)
                return False
            result = resp.json()
            return result.get("valid") is True
    except httpx.RequestError as e:
        logger.error("twilio_request_exception", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Twilio Verify service for validation."
        )
