"""Settings module — API routes."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.settings import schemas, services

router = APIRouter(tags=["Platform Settings"])


# ── Public endpoints ────────────────────────────────────────────────

@router.get("/settings/public", response_model=List[schemas.SettingResponse])
async def public_settings(db: AsyncSession = Depends(get_db)):
    """Get public platform settings (course price, platform name, etc.)."""
    settings_list = await services.get_public_settings(db)
    return [schemas.SettingResponse.model_validate(s) for s in settings_list]


@router.get("/settings/landing-page")
async def get_landing_page(db: AsyncSession = Depends(get_db)):
    """Get landing page CMS config (public — no auth needed)."""
    config = await services.get_landing_page_config(db)
    return config


# ── Admin endpoints ─────────────────────────────────────────────────

@router.get("/admin/settings", response_model=schemas.SettingsGroupedResponse)
async def get_all_settings(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get all settings grouped by category (admin only)."""
    grouped = await services.get_all_settings(db)
    return schemas.SettingsGroupedResponse(
        general=[schemas.SettingResponse.model_validate(s) for s in grouped.get("general", [])],
        simulator=[schemas.SettingResponse.model_validate(s) for s in grouped.get("simulator", [])],
        exam=[schemas.SettingResponse.model_validate(s) for s in grouped.get("exam", [])],
        payment=[schemas.SettingResponse.model_validate(s) for s in grouped.get("payment", [])],
    )


@router.put("/admin/settings/landing-page")
async def update_landing_page(
    body: schemas.LandingPageUpdateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update landing page CMS configuration (admin only)."""
    config = body.model_dump(exclude_unset=True)
    result = await services.update_landing_page_config(db, config, admin.id)
    return result


@router.put("/admin/settings/{key}", response_model=schemas.SettingResponse)
async def update_setting(
    key: str,
    body: schemas.SettingUpdateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a single setting (admin only)."""
    setting = await services.update_setting(db, key, body.value, admin.id)
    return schemas.SettingResponse.model_validate(setting)


@router.put("/admin/settings", response_model=schemas.MessageResponse)
async def bulk_update_settings(
    body: schemas.BulkSettingUpdateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple settings at once (admin only)."""
    count = await services.bulk_update_settings(db, body.settings, admin.id)
    return schemas.MessageResponse(message=f"Updated {count} settings")
