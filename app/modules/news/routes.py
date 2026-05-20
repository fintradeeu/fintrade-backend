"""News module — API routes."""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.database import get_db
from app.modules.auth.models import User
from app.modules.news import schemas, services

router = APIRouter(tags=["News & Content"])


# ── Public endpoints ────────────────────────────────────────────────

@router.get("/news", response_model=List[schemas.NewsResponse])
async def list_published_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List published news articles (public, for homepage)."""
    articles = await services.list_published_news(db, skip, limit)
    return [schemas.NewsResponse.model_validate(a) for a in articles]


@router.get("/news/{article_id}", response_model=schemas.NewsResponse)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single news article (public)."""
    article = await services.get_article(db, article_id)
    return schemas.NewsResponse.model_validate(article)


# ── Admin endpoints ─────────────────────────────────────────────────

@router.get("/admin/news/stats", response_model=schemas.NewsStatsResponse)
async def news_stats(
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get news statistics (admin only)."""
    stats = await services.get_news_stats(db)
    return schemas.NewsStatsResponse(**stats)


@router.get("/admin/news", response_model=List[schemas.NewsResponse])
async def list_all_news(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all news including drafts (admin only)."""
    articles = await services.list_all_news(db, skip, limit)
    return [schemas.NewsResponse.model_validate(a) for a in articles]


@router.post("/admin/news", response_model=schemas.NewsResponse, status_code=201)
async def create_article(
    body: schemas.NewsCreateRequest,
    admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a news article (admin only)."""
    article = await services.create_article(db, body.model_dump(), admin.id)
    return schemas.NewsResponse.model_validate(article)


@router.put("/admin/news/{article_id}", response_model=schemas.NewsResponse)
async def update_article(
    article_id: int,
    body: schemas.NewsUpdateRequest,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a news article (admin only)."""
    article = await services.update_article(db, article_id, body.model_dump(exclude_unset=True))
    return schemas.NewsResponse.model_validate(article)


@router.delete("/admin/news/{article_id}", response_model=schemas.MessageResponse)
async def delete_article(
    article_id: int,
    _admin: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a news article (admin only)."""
    await services.delete_article(db, article_id)
    return schemas.MessageResponse(message="Article deleted successfully")

