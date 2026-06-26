"""Dashboard module — service layer for announcements and advertisements."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.models import Announcement, Advertisement
from app.modules.auth.models import User, Role
from app.modules.exams.models import CourseExamResult
from app.modules.learning.models import LessonCompletion
from app.modules.simulator.models import SimulatorAccount, PerformanceMetric


# ═════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS
# ═════════════════════════════════════════════════════════════════════

async def create_announcement(db: AsyncSession, admin_id: int, data: dict) -> Announcement:
    """Create a new announcement (admin only)."""
    ann = Announcement(
        title=data["title"],
        content=data["content"],
        priority=data.get("priority", "normal"),
        is_active=data.get("is_active", True),
        expires_at=data.get("expires_at"),
        created_by=admin_id,
    )
    db.add(ann)
    await db.flush()
    await db.refresh(ann)
    return ann


async def update_announcement(db: AsyncSession, ann_id: int, data: dict) -> Announcement:
    """Update an existing announcement."""
    ann = await db.get(Announcement, ann_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Announcement not found")

    for key, value in data.items():
        if value is not None:
            setattr(ann, key, value)

    await db.flush()
    await db.refresh(ann)
    return ann


async def delete_announcement(db: AsyncSession, ann_id: int) -> None:
    """Delete an announcement."""
    ann = await db.get(Announcement, ann_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await db.delete(ann)
    await db.flush()


async def list_announcements_admin(db: AsyncSession) -> List[Announcement]:
    """List all announcements (admin view — includes inactive)."""
    result = await db.execute(
        select(Announcement).order_by(Announcement.created_at.desc())
    )
    return list(result.scalars().all())


async def list_active_announcements(db: AsyncSession) -> List[Announcement]:
    """List active, non-expired announcements (student view)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Announcement)
        .where(
            Announcement.is_active == True,
        )
        .order_by(Announcement.priority.desc(), Announcement.published_at.desc())
    )
    announcements = result.scalars().all()
    # Filter expired in Python (nullable expires_at)
    return [a for a in announcements if a.expires_at is None or a.expires_at > now]


# ═════════════════════════════════════════════════════════════════════
# ADVERTISEMENTS
# ═════════════════════════════════════════════════════════════════════

async def create_advertisement(db: AsyncSession, admin_id: int, data: dict) -> Advertisement:
    """Create a new advertisement (admin only)."""
    ad = Advertisement(
        title=data["title"],
        description=data.get("description"),
        image_url=data.get("image_url"),
        link_url=data.get("link_url"),
        placement=data.get("placement", "dashboard"),
        is_active=data.get("is_active", True),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        created_by=admin_id,
    )
    db.add(ad)
    await db.flush()
    await db.refresh(ad)
    return ad


async def update_advertisement(db: AsyncSession, ad_id: int, data: dict) -> Advertisement:
    """Update an existing advertisement."""
    ad = await db.get(Advertisement, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    for key, value in data.items():
        if value is not None:
            setattr(ad, key, value)

    await db.flush()
    await db.refresh(ad)
    return ad


async def delete_advertisement(db: AsyncSession, ad_id: int) -> None:
    """Delete an advertisement."""
    ad = await db.get(Advertisement, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Advertisement not found")
    await db.delete(ad)
    await db.flush()


async def list_advertisements_admin(db: AsyncSession) -> List[Advertisement]:
    """List all advertisements (admin view — includes inactive)."""
    result = await db.execute(
        select(Advertisement).order_by(Advertisement.created_at.desc())
    )
    return list(result.scalars().all())


async def list_active_advertisements(db: AsyncSession, placement: Optional[str] = None) -> List[Advertisement]:
    """List active advertisements within date range (student view)."""
    now = datetime.now(timezone.utc)
    query = select(Advertisement).where(Advertisement.is_active == True)

    if placement:
        query = query.where(Advertisement.placement == placement)

    result = await db.execute(query.order_by(Advertisement.created_at.desc()))
    ads = result.scalars().all()
    # Filter by date range in Python (nullable fields)
    return [
        a for a in ads
        if (a.start_date is None or a.start_date <= now)
        and (a.end_date is None or a.end_date > now)
    ]


# ═════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ═════════════════════════════════════════════════════════════════════

def get_badge(score: float) -> str:
    if score >= 9000: return "Grandmaster"
    if score >= 7500: return "Master"
    if score >= 5000: return "Expert"
    if score >= 3000: return "Pro"
    if score >= 1000: return "Challenger"
    return "Beginner"


async def get_leaderboard(db: AsyncSession, current_user_id: int) -> Dict[str, Any]:
    """Calculate and retrieve global rankings and score for student users."""
    # Aggregate lesson completions
    completions_sub = (
        select(LessonCompletion.user_id, func.count(LessonCompletion.id).label("completed_count"))
        .group_by(LessonCompletion.user_id)
        .subquery()
    )

    # Aggregate exam scores
    exams_sub = (
        select(CourseExamResult.user_id, func.avg(CourseExamResult.percentage).label("avg_percent"))
        .group_by(CourseExamResult.user_id)
        .subquery()
    )

    # Simulator metrics
    sim_sub = (
        select(
            SimulatorAccount.user_id,
            PerformanceMetric.total_pnl,
            PerformanceMetric.winning_trades
        )
        .join(PerformanceMetric, PerformanceMetric.account_id == SimulatorAccount.id)
        .subquery()
    )

    # Query all users with student role
    stmt = (
        select(
            User.id,
            User.full_name,
            func.coalesce(completions_sub.c.completed_count, 0).label("completed_lessons"),
            func.coalesce(exams_sub.c.avg_percent, 0.0).label("exam_avg_percent"),
            func.coalesce(sim_sub.c.total_pnl, 0.0).label("simulator_total_pnl"),
            func.coalesce(sim_sub.c.winning_trades, 0).label("winning_trades"),
        )
        .join(User.roles)
        .outerjoin(completions_sub, completions_sub.c.user_id == User.id)
        .outerjoin(exams_sub, exams_sub.c.user_id == User.id)
        .outerjoin(sim_sub, sim_sub.c.user_id == User.id)
        .where(Role.name == "student")
    )

    result = await db.execute(stmt)
    rows = result.all()

    leaderboard_entries = []
    for r in rows:
        completed_lessons = r.completed_lessons
        exam_avg_percent = r.exam_avg_percent
        total_pnl = r.simulator_total_pnl
        winning_trades = r.winning_trades

        # Formula: (exam_avg_percent * 50) + (completed_lessons * 5) + (winning_trades * 10 if total_pnl > 0 else 0)
        score = (exam_avg_percent * 50) + (completed_lessons * 5)
        if total_pnl > 0:
            score += winning_trades * 10

        score_int = int(round(score))

        leaderboard_entries.append({
            "id": r.id,
            "name": r.full_name,
            "score": score_int,
            "rank": 0,
            "badge": get_badge(score_int)
        })

    # Sort by score descending, then name
    leaderboard_entries.sort(key=lambda x: (-x["score"], x["name"]))

    # Assign ranks
    for idx, entry in enumerate(leaderboard_entries):
        entry["rank"] = idx + 1

    # Locate current user's rank/score
    my_rank = 0
    my_score = 0
    for entry in leaderboard_entries:
        if entry["id"] == current_user_id:
            my_rank = entry["rank"]
            my_score = entry["score"]
            break

    return {
        "leaderboard": leaderboard_entries,
        "my_rank": my_rank,
        "my_score": my_score
    }
