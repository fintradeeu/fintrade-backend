"""Dashboard module — API routes for announcements and advertisements."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.dashboard import schemas, services

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ═════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS — Student-facing
# ═════════════════════════════════════════════════════════════════════

@router.get("/announcements", response_model=List[schemas.AnnouncementResponse])
async def list_announcements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active announcements for the dashboard."""
    items = await services.list_active_announcements(db)
    return [schemas.AnnouncementResponse.model_validate(a) for a in items]


# ═════════════════════════════════════════════════════════════════════
# ADVERTISEMENTS — Student-facing
# ═════════════════════════════════════════════════════════════════════

@router.get("/advertisements", response_model=List[schemas.AdvertisementResponse])
async def list_advertisements(
    placement: Optional[str] = Query(None, description="Filter by placement: dashboard, sidebar, banner"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active advertisements for the dashboard."""
    items = await services.list_active_advertisements(db, placement=placement)
    return [schemas.AdvertisementResponse.model_validate(a) for a in items]


# ═════════════════════════════════════════════════════════════════════
# LEADERBOARD — Student-facing
# ═════════════════════════════════════════════════════════════════════

@router.get("/leaderboard", response_model=schemas.LeaderboardResponse)
async def get_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the global leaderboard rankings, score, and current user rank."""
    data = await services.get_leaderboard(db, current_user.id)
    return schemas.LeaderboardResponse(**data)


# ═════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS — Admin CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/admin/announcements", response_model=List[schemas.AnnouncementResponse])
async def admin_list_announcements(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all announcements including inactive (admin only)."""
    items = await services.list_announcements_admin(db)
    return [schemas.AnnouncementResponse.model_validate(a) for a in items]


@router.post("/admin/announcements", response_model=schemas.AnnouncementResponse, status_code=201)
async def create_announcement(
    req: schemas.AnnouncementCreateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new announcement (admin only)."""
    ann = await services.create_announcement(db, admin.id, req.model_dump())
    return schemas.AnnouncementResponse.model_validate(ann)


@router.put("/admin/announcements/{ann_id}", response_model=schemas.AnnouncementResponse)
async def update_announcement(
    ann_id: int,
    req: schemas.AnnouncementUpdateRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update an announcement (admin only)."""
    ann = await services.update_announcement(db, ann_id, req.model_dump(exclude_unset=True))
    return schemas.AnnouncementResponse.model_validate(ann)


@router.delete("/admin/announcements/{ann_id}", response_model=schemas.MessageResponse)
async def delete_announcement(
    ann_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete an announcement (admin only)."""
    await services.delete_announcement(db, ann_id)
    return schemas.MessageResponse(message="Announcement deleted")


# ═════════════════════════════════════════════════════════════════════
# ADVERTISEMENTS — Admin CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/admin/advertisements", response_model=List[schemas.AdvertisementResponse])
async def admin_list_advertisements(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all advertisements including inactive (admin only)."""
    items = await services.list_advertisements_admin(db)
    return [schemas.AdvertisementResponse.model_validate(a) for a in items]


@router.post("/admin/advertisements", response_model=schemas.AdvertisementResponse, status_code=201)
async def create_advertisement(
    req: schemas.AdvertisementCreateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new advertisement (admin only)."""
    ad = await services.create_advertisement(db, admin.id, req.model_dump())
    return schemas.AdvertisementResponse.model_validate(ad)


@router.put("/admin/advertisements/{ad_id}", response_model=schemas.AdvertisementResponse)
async def update_advertisement(
    ad_id: int,
    req: schemas.AdvertisementUpdateRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update an advertisement (admin only)."""
    ad = await services.update_advertisement(db, ad_id, req.model_dump(exclude_unset=True))
    return schemas.AdvertisementResponse.model_validate(ad)


@router.delete("/admin/advertisements/{ad_id}", response_model=schemas.MessageResponse)
async def delete_advertisement(
    ad_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete an advertisement (admin only)."""
    await services.delete_advertisement(db, ad_id)
    return schemas.MessageResponse(message="Advertisement deleted")
