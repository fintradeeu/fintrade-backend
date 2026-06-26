import logging
from typing import Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_whatsapp_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    return digits


async def send_whatsapp_message(to_phone: str, template_name: str, template_data: Dict[str, Any] = None) -> bool:
    """
    Stub for sending WhatsApp Template Messages via Meta/Twilio API.
    Used for student reminders (e.g. class starting, assignment due).
    
    Args:
        to_phone: The recipient's phone number with country code.
        template_name: The registered WhatsApp template name.
        template_data: Dynamic parameters for the template.
    """
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("[WhatsApp] API token or phone number ID not configured. Skipped '%s' to %s", template_name, to_phone)
        return False

    normalized_phone = _normalize_whatsapp_phone(to_phone)
    if not normalized_phone:
        logger.warning("[WhatsApp] Missing recipient phone for template '%s'", template_name)
        return False

    parameters = [
        {"type": "text", "text": str(value)}
        for value in (template_data or {}).values()
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": normalized_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANGUAGE},
        },
    }
    if parameters:
        payload["template"]["components"] = [
            {
                "type": "body",
                "parameters": parameters,
            }
        ]

    url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            logger.error("[WhatsApp] Failed template=%s to=%s status=%s body=%s", template_name, normalized_phone, response.status_code, response.text)
            return False
        logger.info("[WhatsApp] Sent template=%s to=%s", template_name, normalized_phone)
        return True
    except Exception as exc:
        logger.error("[WhatsApp] Error sending template=%s to=%s error=%s", template_name, normalized_phone, exc)
        return False

async def send_reminder_for_lecture(student_phone: str, lecture_title: str, time_str: str) -> bool:
    """Convenience function to dispatch a lecture reminder."""
    return await send_whatsapp_message(
        to_phone=student_phone,
        template_name="lecture_reminder",
        template_data={"title": lecture_title, "time": time_str}
    )


async def send_lecture_finished_message(
    student_phone: str,
    student_name: str,
    lecture_title: str,
    course_title: str,
    finished_at: str,
) -> bool:
    """Dispatch the lecture-finished WhatsApp template."""
    return await send_whatsapp_message(
        to_phone=student_phone,
        template_name="lecture_finished",
        template_data={
            "student_name": student_name,
            "lecture_title": lecture_title,
            "course_title": course_title,
            "finished_at": finished_at,
        },
    )
