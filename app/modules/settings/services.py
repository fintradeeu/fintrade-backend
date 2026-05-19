"""Settings module — business logic / services."""

import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import PlatformSetting


# Default settings to seed if table is empty
DEFAULT_SETTINGS = [
    {"key": "platform_name", "value": "FinTrade", "category": "general", "label": "Platform Name"},
    {"key": "support_email", "value": "support@fintrade.com", "category": "general", "label": "Support Email"},
    {"key": "default_course_price", "value": "25000", "category": "payment", "label": "Default Course Price (₹)"},
    {"key": "exam_retake_fee", "value": "300", "category": "payment", "label": "Exam Retake Fee (₹)"},
    {"key": "starting_capital", "value": "500000", "category": "simulator", "label": "Starting Capital (₹)"},
    {"key": "daily_loss_limit", "value": "10000", "category": "simulator", "label": "Daily Loss Limit (₹)"},
    {"key": "passing_score", "value": "60", "category": "exam", "label": "Passing Score (%)"},
    {"key": "max_attempts", "value": "3", "category": "exam", "label": "Max Attempts Per Exam"},
]

DEFAULT_LANDING_PAGE_CONFIG = {
    "hero": {
        "title": "India's Trading",
        "highlight": "Powerhouse",
        "subtitle": "We are not building another trading course company. We are building India's first Trader-to-Funded Professional Pipeline — where every student has a pathway to professional capital.",
        "badge": "🎯 India's Premier Trading Education",
    },
    "contact": {
        "phone": "+91 98765 43210",
        "phone_href": "tel:+919876543210",
    },
    "social": {
        "instagram": "https://www.instagram.com/the.fintrade/",
        "facebook": "https://www.facebook.com/profile.php?id=61589528075521",
        "youtube": "https://www.youtube.com/@The_FinTrade",
        "linkedin": "https://www.linkedin.com/in/the-fintrade-7230b040a/",
    },
    "showcase_videos": [
        {
            "title": "FinTrade Student Story",
            "subtitle": "From Zero to Prop Trader in 9 Months",
            "duration": "3:24",
            "thumbnail": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "url": "",
        },
        {
            "title": "Trading Simulator Walkthrough",
            "subtitle": "Experience Real Markets, Zero Risk",
            "duration": "2:10",
            "thumbnail": "https://images.unsplash.com/photo-1612178991541-b48cc8e92a4d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "url": "",
        },
        {
            "title": "What Our Alumni Say",
            "subtitle": "Hear from Placed Traders",
            "duration": "4:55",
            "thumbnail": "https://images.unsplash.com/photo-1659353221405-29b7d087f9e5?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "url": "",
        },
    ],
}


async def ensure_defaults(db: AsyncSession) -> None:
    """Seed default settings if table is empty."""
    result = await db.execute(select(PlatformSetting))
    existing = result.scalars().all()
    if existing:
        return

    for s in DEFAULT_SETTINGS:
        db.add(PlatformSetting(**s))
    await db.commit()


async def get_public_settings(db: AsyncSession) -> List[PlatformSetting]:
    """Get settings that are safe for public (general + payment category)."""
    await ensure_defaults(db)
    result = await db.execute(
        select(PlatformSetting).where(
            PlatformSetting.category.in_(["general", "payment"])
        )
    )
    return result.scalars().all()


async def get_all_settings(db: AsyncSession) -> Dict[str, List[PlatformSetting]]:
    """Get all settings grouped by category (admin)."""
    await ensure_defaults(db)
    result = await db.execute(
        select(PlatformSetting).order_by(PlatformSetting.category, PlatformSetting.key)
    )
    settings = result.scalars().all()

    grouped = {"general": [], "simulator": [], "exam": [], "payment": []}
    for s in settings:
        category = s.category or "general"
        if category in grouped:
            grouped[category].append(s)
        else:
            grouped["general"].append(s)
    return grouped


async def update_setting(db: AsyncSession, key: str, value: str, admin_id: int) -> PlatformSetting:
    """Update a single setting by key."""
    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    setting.value = value
    setting.updated_by = admin_id
    await db.commit()
    await db.refresh(setting)
    return setting


async def bulk_update_settings(db: AsyncSession, settings: Dict[str, str], admin_id: int) -> int:
    """Update multiple settings at once. Returns count of updated settings."""
    updated = 0
    for key, value in settings.items():
        result = await db.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            setting.updated_by = admin_id
            updated += 1

    await db.commit()
    return updated


# ── Landing Page CMS ─────────────────────────────────────────────────

LANDING_PAGE_KEY = "landing_page_config"


async def get_landing_page_config(db: AsyncSession) -> Dict[str, Any]:
    """Get landing page CMS config. Returns defaults if not yet configured."""
    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.key == LANDING_PAGE_KEY)
    )
    setting = result.scalar_one_or_none()
    if not setting or not setting.value:
        return DEFAULT_LANDING_PAGE_CONFIG
    try:
        return json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_LANDING_PAGE_CONFIG


async def update_landing_page_config(
    db: AsyncSession, config: Dict[str, Any], admin_id: int
) -> Dict[str, Any]:
    """Update the landing page CMS config (admin only)."""
    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.key == LANDING_PAGE_KEY)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        setting = PlatformSetting(
            key=LANDING_PAGE_KEY,
            value=json.dumps(config),
            category="general",
            label="Landing Page Content",
            updated_by=admin_id,
        )
        db.add(setting)
    else:
        existing: Dict[str, Any] = {}
        if setting.value:
            try:
                existing = json.loads(setting.value)
            except (json.JSONDecodeError, TypeError):
                existing = {}
        existing.update(config)
        setting.value = json.dumps(existing)
        setting.updated_by = admin_id

    await db.commit()
    result2 = await db.execute(
        select(PlatformSetting).where(PlatformSetting.key == LANDING_PAGE_KEY)
    )
    s = result2.scalar_one()
    return json.loads(s.value)
