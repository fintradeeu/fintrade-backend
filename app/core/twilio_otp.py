"""SMS OTP gateway wrappers for Nimbus, Fast2SMS, and Twilio Verify."""

import json

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


def clean_phone_for_fast2sms(phone: str) -> str:
    """Ensure phone number is a 10-digit string for Fast2SMS."""
    cleaned = "".join(c for c in phone if c.isdigit())
    if len(cleaned) > 10:
        # Strip country code (e.g. 91) or just take the last 10 digits
        if cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        else:
            cleaned = cleaned[-10:]
    return cleaned


def clean_phone_for_nimbus(phone: str) -> str:
    """Ensure phone number is in 91xxxxxxxxxx format (without leading +) for Nimbus."""
    cleaned = "".join(c for c in phone if c.isdigit())
    if len(cleaned) == 10:
        cleaned = f"91{cleaned}"
    elif len(cleaned) > 10:
        if not cleaned.startswith("91"):
            cleaned = f"91{cleaned[-10:]}"
    return cleaned


def print_fallback_otp(phone: str, code: str, reason: str):
    logger.warning("sms_delivery_failed_falling_back_to_console", phone=phone, reason=reason)
    print("\n" + "="*80)
    print(f"  [SMS DELIVERY FAILURE] SMS could not be sent to {phone}")
    print(f"  REASON: {reason}")
    print(f"  GENERATED OTP CODE FOR DEV/TESTING (ENTER THIS CODE): {code}")
    print("="*80 + "\n")


def _build_fast2sms_message(code: str) -> str:
    return f"{code} is your FinTrade verification code. Valid for {settings.OTP_EXPIRY_MINUTES} min. Do not share this code."


def _build_nimbus_message(code: str) -> str:
    return settings.NIMBUS_SMS_MESSAGE_TEMPLATE.format(
        code=code,
        expiry_minutes=settings.OTP_EXPIRY_MINUTES,
    )


def _is_nimbus_success_response(response_text: str) -> bool:
    normalized = response_text.strip().lower()
    if not normalized:
        return False

    try:
        data = json.loads(response_text)
        status_value = str(data.get("Status", "")).strip().lower()
        response = data.get("Response") or {}
        message_value = str(response.get("Message", "")).strip().lower()
        if status_value == "ok" and ("message id" in message_value or message_value):
            return True
    except (TypeError, ValueError):
        pass

    error_markers = (
        "invalid",
        "error",
        "fail",
        "failed",
        "insufficient",
        "unauthorized",
        "not found",
        "template",
        "sender",
        "balance",
    )
    if any(marker in normalized for marker in error_markers):
        return False

    success_markers = (
        "success",
        "sent",
        "submitted",
        "accepted",
        "queued",
        "done",
    )
    return any(marker in normalized for marker in success_markers) or normalized in {"1", "true", "ok"}


def _extract_nimbus_message_id(response_text: str) -> str | None:
    try:
        data = json.loads(response_text)
    except (TypeError, ValueError):
        return None

    response = data.get("Response") or {}
    message = str(response.get("Message", "")).strip()
    if not message:
        return None

    _, separator, message_id = message.partition(":")
    return message_id.strip() if separator else message


def _short_response(response_text: str) -> str:
    text = " ".join(response_text.split())
    return text[:500]


def is_local_sms_otp_enabled() -> bool:
    """Return true when SMS OTP codes are generated and verified by this backend."""
    return is_nimbus_sms_configured() or bool(settings.FAST2SMS_API_KEY)


def is_nimbus_sms_configured() -> bool:
    """Return true when the Nimbus SMS gateway has all required credentials."""
    return bool(
        settings.NIMBUS_SMS_USER_ID
        and settings.NIMBUS_SMS_PASSWORD
        and settings.NIMBUS_SMS_SENDER_ID
        and settings.NIMBUS_SMS_ENTITY_ID
        and settings.NIMBUS_SMS_TEMPLATE_ID
    )


async def send_nimbus_otp(phone: str, code: str) -> bool:
    """Send verification OTP using the Nimbus SendSingleApi endpoint."""
    if not is_nimbus_sms_configured():
        logger.warning("nimbus_sms_skipped", reason="Nimbus SMS credentials not configured")
        return False

    phone_clean = clean_phone_for_nimbus(phone)
    params = {
        "UserID": settings.NIMBUS_SMS_USER_ID,
        "Password": settings.NIMBUS_SMS_PASSWORD,
        "SenderID": settings.NIMBUS_SMS_SENDER_ID,
        "Phno": phone_clean,
        "Msg": _build_nimbus_message(code),
        "EntityID": settings.NIMBUS_SMS_ENTITY_ID,
        "TemplateID": settings.NIMBUS_SMS_TEMPLATE_ID,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.NIMBUS_SMS_BASE_URL, params=params, timeout=10.0)
            if resp.status_code != 200:
                logger.error("nimbus_sms_send_error", status_code=resp.status_code, body=resp.text)
                print_fallback_otp(phone_clean, code, f"Nimbus HTTP status {resp.status_code}")
                return False

            if not _is_nimbus_success_response(resp.text):
                response_summary = _short_response(resp.text)
                logger.error("nimbus_sms_api_error", response=response_summary)
                print_fallback_otp(phone_clean, code, f"Nimbus API did not confirm delivery: {response_summary}")
                return False

            logger.info(
                "nimbus_sms_otp_sent_successfully",
                phone=phone_clean[-4:],
                provider_message_id=_extract_nimbus_message_id(resp.text),
            )
            return True
    except Exception as e:
        logger.error("nimbus_sms_request_exception", error=str(e))
        print_fallback_otp(phone_clean, code, str(e))
        return False


async def _send_fast2sms_request(
    params: dict,
    phone_clean: str,
    code: str,
    route_name: str,
    show_console_fallback: bool = True,
) -> bool:
    url = "https://www.fast2sms.com/dev/bulkV2"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10.0)
            if resp.status_code != 200:
                logger.error(
                    "fast2sms_send_error",
                    route=route_name,
                    status_code=resp.status_code,
                    body=resp.text,
                )
                if show_console_fallback:
                    print_fallback_otp(phone_clean, code, f"HTTP status {resp.status_code}: {resp.text}")
                return False

            result = resp.json()
            if not result.get("return"):
                logger.error("fast2sms_api_error", route=route_name, response=result)
                if show_console_fallback:
                    print_fallback_otp(phone_clean, code, f"API error: {result.get('message', 'Unknown error')}")
                return False

            logger.info("fast2sms_otp_sent_successfully", phone=phone_clean[-4:], route=route_name)
            return True
    except Exception as e:
        logger.error("fast2sms_request_exception", route=route_name, error=str(e))
        if show_console_fallback:
            print_fallback_otp(phone_clean, code, str(e))
        return False


async def send_fast2sms_otp(phone: str, code: str) -> bool:
    """Send verification OTP using Fast2SMS bulkV2 API."""
    if not settings.FAST2SMS_API_KEY:
        logger.warning("fast2sms_skipped", reason="Fast2SMS API key not configured")
        return False

    phone_clean = clean_phone_for_fast2sms(phone)
    
    # Check if we are using the otp route or the dlt route
    route = settings.FAST2SMS_ROUTE.lower()
    
    params = {
        "authorization": settings.FAST2SMS_API_KEY,
        "route": route,
        "numbers": phone_clean,
    }
    
    if route == "dlt":
        # DLT route requires sender_id and message template ID
        if not settings.FAST2SMS_SENDER_ID or not settings.FAST2SMS_MESSAGE_ID:
            logger.error("fast2sms_dlt_error", error="FAST2SMS_SENDER_ID or FAST2SMS_MESSAGE_ID not configured for DLT route")
            logger.warning("fast2sms_dlt_fallback_to_quick_route", phone=phone_clean)
            route = "q"
            params["route"] = route
            params["message"] = _build_fast2sms_message(code)
            return await _send_fast2sms_request(params, phone_clean, code, route)
        params["sender_id"] = settings.FAST2SMS_SENDER_ID
        params["message"] = settings.FAST2SMS_MESSAGE_ID
        params["variables_values"] = code
    elif route in ("q", "quick"):
        params["route"] = "q"
        params["message"] = _build_fast2sms_message(code)
    else:
        # Standard OTP route
        params["route"] = "otp"
        params["variables_values"] = code

    sent = await _send_fast2sms_request(params, phone_clean, code, route, show_console_fallback=False)
    if sent:
        return True

    # Fast2SMS blocks the OTP route on some accounts until a paid transaction is completed.
    # When that happens, retry with the plain-text quick route so the code still reaches the phone.
    if route == "otp":
        fallback_params = {
            "authorization": settings.FAST2SMS_API_KEY,
            "route": "q",
            "numbers": phone_clean,
            "message": _build_fast2sms_message(code),
        }
        logger.warning("fast2sms_retrying_with_quick_route", phone=phone_clean)
        return await _send_fast2sms_request(fallback_params, phone_clean, code, "q", show_console_fallback=True)

    return False


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


async def send_sms_otp(phone: str, code: str) -> bool:
    """Send SMS OTP using configured gateway.

    Nimbus and Fast2SMS send backend-generated codes. Twilio Verify manages its
    own code lifecycle and is used only when no local-code gateway is configured.
    """
    if is_nimbus_sms_configured():
        return await send_nimbus_otp(phone, code)
    if settings.FAST2SMS_API_KEY:
        return await send_fast2sms_otp(phone, code)
    return await send_twilio_otp(phone)


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
