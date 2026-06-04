"""News module — API routes.

URL structure (unchanged — frontend depends on these):

  Public
  ------
  GET  /news                      List published articles
  GET  /news/{id}                 Get single article (increments views)

  Admin
  -----
  GET  /admin/news                List all articles (incl. drafts)
  POST /admin/news                Create article
  PUT  /admin/news/{id}           Update article
  DELETE /admin/news/{id}         Delete article
  GET  /admin/news/stats          Aggregate stats
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.news import schemas, services

router = APIRouter(tags=["News & Content"])


# ════════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS
# ════════════════════════════════════════════════════════════

@router.get("/news", response_model=List[schemas.NewsResponse])
async def list_published_news(
    type: Optional[str] = Query(None, description="Filter by type: 'Market Update' or 'Blog Story'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List published news articles (public — used on homepage / blog page)."""
    articles = await services.list_published_news(db, article_type=type, skip=skip, limit=limit)
    return [schemas.NewsResponse.model_validate(a) for a in articles]


@router.get("/news/{article_id}", response_model=schemas.NewsResponse)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single published article and record a view (public)."""
    article = await services.get_article(db, article_id)
    return schemas.NewsResponse.model_validate(article)


# ════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ════════════════════════════════════════════════════════════

@router.get("/admin/news/stats", response_model=schemas.NewsStatsResponse)
async def news_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for Market Updates & Blog Stories (admin only)."""
    stats = await services.get_news_stats(db)
    return schemas.NewsStatsResponse(**stats)


@router.get("/admin/news", response_model=List[schemas.NewsResponse])
async def list_all_news(
    type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all articles including drafts (admin only)."""
    articles = await services.list_all_news(db, article_type=type, status=status, skip=skip, limit=limit)
    return [schemas.NewsResponse.model_validate(a) for a in articles]


@router.post("/admin/news", response_model=schemas.NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    body: schemas.NewsCreateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a Market Update or Blog Story (admin only)."""
    data = body.model_dump()
    perms = admin.permissions if isinstance(admin.permissions, dict) else {}
    is_super = admin.email == "admin@platform.com" or perms.get("roleName") == "Super Admin"
    direct_publish = perms.get("directPublish", True if is_super else False)
    if not direct_publish:
        data["status"] = "draft"
    article = await services.create_article(db, data, admin.id)
    return schemas.NewsResponse.model_validate(article)


@router.put("/admin/news/{article_id}", response_model=schemas.NewsResponse)
async def update_article(
    article_id: int,
    body: schemas.NewsUpdateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a Market Update or Blog Story (admin only)."""
    data = body.model_dump(exclude_unset=True)
    perms = admin.permissions if isinstance(admin.permissions, dict) else {}
    is_super = admin.email == "admin@platform.com" or perms.get("roleName") == "Super Admin"
    direct_publish = perms.get("directPublish", True if is_super else False)
    if not direct_publish:
        data["status"] = "draft"
    article = await services.update_article(db, article_id, data)
    return schemas.NewsResponse.model_validate(article)


@router.delete("/admin/news/{article_id}", response_model=schemas.MessageResponse)
async def delete_article(
    article_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an article (admin only)."""
    await services.delete_article(db, article_id)
    return schemas.MessageResponse(message="Article deleted successfully")
