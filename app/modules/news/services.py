"""News module — business logic / services."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.models import NewsArticle


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, article_id: int) -> NewsArticle:
    result = await db.execute(select(NewsArticle).where(NewsArticle.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


# ── Public ───────────────────────────────────────────────────────────────────

async def list_published_news(
    db: AsyncSession,
    article_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> List[NewsArticle]:
    """Return published articles, optionally filtered by type."""
    q = select(NewsArticle).where(NewsArticle.status == "published")
    if article_type:
        q = q.where(NewsArticle.type == article_type)
    q = q.order_by(NewsArticle.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_article(db: AsyncSession, article_id: int) -> NewsArticle:
    """Return a single article and increment its view counter."""
    article = await _get_or_404(db, article_id)
    article.views_count = (article.views_count or 0) + 1
    await db.commit()
    await db.refresh(article)
    return article


# ── Admin: list ───────────────────────────────────────────────────────────────

async def list_all_news(
    db: AsyncSession,
    article_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[NewsArticle]:
    """Return all articles (including drafts) for admin, with optional filters."""
    q = select(NewsArticle)
    if article_type:
        q = q.where(NewsArticle.type == article_type)
    if status:
        q = q.where(NewsArticle.status == status)
    q = q.order_by(NewsArticle.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


# ── Admin: CRUD ───────────────────────────────────────────────────────────────

async def create_article(
    db: AsyncSession,
    data: dict,
    created_by: int,
) -> NewsArticle:
    """Create a new news article."""
    # For Blog Stories, clear any video_url that was accidentally sent
    if data.get("type") == "Blog Story":
        data["video_url"] = None

    article = NewsArticle(created_by=created_by, **data)
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


async def update_article(
    db: AsyncSession,
    article_id: int,
    data: dict,
) -> NewsArticle:
    """Update an existing article (partial update)."""
    article = await _get_or_404(db, article_id)

    for key, value in data.items():
        if hasattr(article, key):
            setattr(article, key, value)

    # Enforce: Blog Stories must not have a video_url
    if article.type == "Blog Story":
        article.video_url = None

    await db.commit()
    await db.refresh(article)
    return article


async def delete_article(db: AsyncSession, article_id: int) -> None:
    """Permanently delete an article."""
    article = await _get_or_404(db, article_id)
    await db.delete(article)
    await db.commit()


# ── Admin: stats ──────────────────────────────────────────────────────────────

async def get_news_stats(db: AsyncSession) -> dict:
    """Return aggregate stats for the admin dashboard."""
    result = await db.execute(select(NewsArticle))
    articles = list(result.scalars().all())

    return {
        "total_articles":      len(articles),
        "market_update_count": sum(1 for a in articles if a.type == "Market Update"),
        "blog_story_count":    sum(1 for a in articles if a.type == "Blog Story"),
        "published_count":     sum(1 for a in articles if a.status == "published"),
        "draft_count":         sum(1 for a in articles if a.status == "draft"),
        "total_views":         sum(a.views_count or 0 for a in articles),
    }
