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


@router.get("/settings/about-us", response_model=schemas.AboutUsConfig)
async def get_about_us(db: AsyncSession = Depends(get_db)):
    """Get specifically the About Us page content from CMS (public)."""
    config = await services.get_landing_page_config(db)
    return schemas.AboutUsConfig(
        slides=config.get("about_us_slides"),
        stats=config.get("about_us_stats"),
        text=config.get("about_us_text"),
        vision=config.get("about_us_vision"),
        mission=config.get("about_us_mission"),
        leadership=config.get("leadership")
    )


@router.put("/admin/settings/about-us", response_model=schemas.AboutUsConfig)
async def update_about_us(
    body: schemas.AboutUsConfig,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update specifically the About Us page content in CMS (admin only)."""
    config_update = {}
    if body.slides is not None:
        config_update["about_us_slides"] = body.slides
    if body.stats is not None:
        config_update["about_us_stats"] = body.stats
    if body.text is not None:
        config_update["about_us_text"] = body.text
    if body.vision is not None:
        config_update["about_us_vision"] = body.vision
    if body.mission is not None:
        config_update["about_us_mission"] = body.mission
    if body.leadership is not None:
        config_update["leadership"] = body.leadership
        
    updated_config = await services.update_landing_page_config(db, config_update, admin.id)
    
    return schemas.AboutUsConfig(
        slides=updated_config.get("about_us_slides"),
        stats=updated_config.get("about_us_stats"),
        text=updated_config.get("about_us_text"),
        vision=updated_config.get("about_us_vision"),
        mission=updated_config.get("about_us_mission"),
        leadership=updated_config.get("leadership")
    )


@router.get("/settings/advisors", response_model=schemas.AdvisorsConfig)
async def get_advisors(db: AsyncSession = Depends(get_db)):
    """Get the advisors/leadership list for the public website (public)."""
    config = await services.get_landing_page_config(db)
    return schemas.AdvisorsConfig(advisors=config.get("advisors", []))


@router.put("/admin/settings/advisors", response_model=schemas.AdvisorsConfig)
async def update_advisors(
    body: schemas.AdvisorsConfig,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update the advisors/leadership list (admin only)."""
    config_update = {"advisors": body.advisors if body.advisors is not None else []}
    updated_config = await services.update_landing_page_config(db, config_update, admin.id)
    return schemas.AdvisorsConfig(advisors=updated_config.get("advisors", []))


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
