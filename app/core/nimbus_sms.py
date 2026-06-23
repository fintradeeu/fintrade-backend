"""Nimbus SMS API wrapper for sending OTPs."""

import httpx
from fastapi import HTTPException, status
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def clean_phone_number(phone: str) -> str:
    """Ensure phone number is just 10 digits for Indian SMS gateways, or strip country prefix."""
    cleaned = phone.strip()
    # Keep only digits
    cleaned = "".join(c for c in cleaned if c.isdigit())
    
    # If it starts with 91 and is 12 digits long, strip the 91
    if len(cleaned) == 12 and cleaned.startswith("91"):
        cleaned = cleaned[2:]
    elif len(cleaned) > 10:
        # Just take the last 10 digits
        cleaned = cleaned[-10:]
        
    return cleaned


async def send_nimbus_sms(phone: str, message: str) -> bool:
    """Send an SMS message via Nimbus SMS API."""
    phone_clean = clean_phone_number(phone)
    
    if not settings.NIMBUS_SMS_USER_ID or not settings.NIMBUS_SMS_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nimbus SMS gateway is not configured on the server."
        )

    # Construct redundant query parameters to ensure compatibility with different parameter names
    params = {
        # Username variations
        "username": settings.NIMBUS_SMS_USER_ID,
        "UserID": settings.NIMBUS_SMS_USER_ID,
        "user": settings.NIMBUS_SMS_USER_ID,
        
        # Password variations
        "password": settings.NIMBUS_SMS_PASSWORD,
        "Password": settings.NIMBUS_SMS_PASSWORD,
        
        # Sender ID variations
        "sender": settings.NIMBUS_SMS_SENDER_ID,
        "senderid": settings.NIMBUS_SMS_SENDER_ID,
        "SenderID": settings.NIMBUS_SMS_SENDER_ID,
        
        # Phone number variations
        "mobile": phone_clean,
        "mobilenumber": phone_clean,
        "MobileNo": phone_clean,
        "PhNo": phone_clean,
        "phone": phone_clean,
        
        # Message variations
        "message": message,
        "Message": message,
        "msg": message,
        "Msg": message,
        
        # DLT Entity ID variations
        "entityid": settings.NIMBUS_SMS_ENTITY_ID,
        "EntityID": settings.NIMBUS_SMS_ENTITY_ID,
        
        # DLT Template ID variations
        "templateid": settings.NIMBUS_SMS_TEMPLATE_ID,
        "TemplateID": settings.NIMBUS_SMS_TEMPLATE_ID,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.NIMBUS_SMS_BASE_URL, params=params, timeout=10.0)
            if resp.status_code not in (200, 201):
                logger.error("nimbus_send_error", status_code=resp.status_code, body=resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Nimbus SMS sending failed: {resp.text}"
                )
            logger.info("nimbus_sms_sent_successfully", phone=phone_clean, response=resp.text)
            return True
    except httpx.RequestError as e:
        logger.error("nimbus_request_exception", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Nimbus SMS service."
        )
