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
    "benefits": [
        {
            "num": "01",
            "title": "Full Trading Program",
            "desc": "Institutional curriculum from foundations to professional-level execution.",
            "icon": "BookOpen"
        },
        {
            "num": "02",
            "title": "3 Tested Strategies",
            "desc": "Three proven, back-tested trading strategies for consistent performance.",
            "icon": "TrendingUp"
        },
        {
            "num": "03",
            "title": "Risk Policy Manual",
            "desc": "Comprehensive risk management guidelines to protect capital at all times.",
            "icon": "FileText"
        },
        {
            "num": "04",
            "title": "Performance Audit System",
            "desc": "Structured periodic audits to track, analyze and improve your trading.",
            "icon": "BarChart3"
        },
        {
            "num": "05",
            "title": "Simulated $200k Account",
            "desc": "Practice with a $200,000 simulated prop account to build confidence.",
            "icon": "Shield"
        },
        {
            "num": "06",
            "title": "90 Day Performance Report",
            "desc": "Detailed 90-day performance review with actionable improvement insights.",
            "icon": "Award"
        },
        {
            "num": "07",
            "title": "Control Drawdown",
            "desc": "Learn to manage and minimize drawdown through disciplined trading rules.",
            "icon": "Target"
        },
        {
            "num": "08",
            "title": "Manage 5-7 Figure Capital",
            "desc": "Training to confidently handle large institutional-scale capital.",
            "icon": "Trophy"
        },
        {
            "num": "09",
            "title": "Management",
            "desc": "Holistic trading management skills covering psychology, strategy and ops.",
            "icon": "Brain"
        }
    ],
    "services": [
        {
            "icon": "UserCheck",
            "title": "Mentor",
            "desc": "One-on-one expert guidance from seasoned market professionals."
        },
        {
            "icon": "Monitor",
            "title": "Online Class",
            "desc": "Live, interactive online sessions accessible from anywhere."
        },
        {
            "icon": "Wifi",
            "title": "Live Market Sessions",
            "desc": "Real-time market participation and analysis with experts."
        },
        {
            "icon": "Activity",
            "title": "Real Time Trading",
            "desc": "Hands-on trading during live market hours under supervision."
        },
        {
            "icon": "ClipboardCheck",
            "title": "Practical Evaluation",
            "desc": "Structured assessments to measure and certify your progress."
        },
        {
            "icon": "GitBranch",
            "title": "Strategy Building",
            "desc": "Develop personalised trading strategies backed by data."
        },
        {
            "icon": "Cpu",
            "title": "AI-Integrated Financial Course",
            "desc": "Modern curriculum powered by AI tools and analytical methods."
        },
        {
            "icon": "LineChart",
            "title": "AI-Analytics",
            "desc": "Leverage AI-driven analytics for smarter market insights."
        }
    ],
    "quick_tips": [
        {
            "id": "v1",
            "num": "#1",
            "title": "How I Became a Funded Trader",
            "author": "Rahul S.",
            "views": "12K",
            "thumbnail": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        },
        {
            "id": "v2",
            "num": "#2",
            "title": "My First Profitable Trade",
            "author": "Priya V.",
            "views": "8.5K",
            "thumbnail": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        },
        {
            "id": "v3",
            "num": "#3",
            "title": "Risk Management Tips",
            "author": "Amit P.",
            "views": "15K",
            "thumbnail": "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        },
        {
            "id": "v4",
            "num": "#4",
            "title": "Technical Analysis Basics",
            "author": "Karan M.",
            "views": "9.2K",
            "thumbnail": "https://images.unsplash.com/photo-1616587896649-79b16d8b173d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        },
        {
            "id": "v5",
            "num": "#5",
            "title": "Day Trading Routine",
            "author": "Sneha R.",
            "views": "11K",
            "thumbnail": "https://images.unsplash.com/photo-1640340434855-6084b1f4901c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        },
        {
            "id": "v6",
            "num": "#6",
            "title": "NIFTY Analysis Explained",
            "author": "Vikram D.",
            "views": "7.8K",
            "thumbnail": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800",
            "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        }
    ],
    "why_choose": [
        {
            "num": "01",
            "title": "AI Tutor Support",
            "desc": "Get personalized AI-powered guidance throughout your learning journey with real-time doubt resolution.",
            "icon": "Brain"
        },
        {
            "num": "02",
            "title": "Structured Curriculum",
            "desc": "Follow a proven step-by-step curriculum designed by industry professionals and expert traders.",
            "icon": "BookOpen"
        },
        {
            "num": "03",
            "title": "Real Trading Simulation",
            "desc": "Practice with our advanced trading simulator using virtual capital in real market conditions.",
            "icon": "LineChart"
        },
        {
            "num": "04",
            "title": "Placement Opportunities",
            "desc": "Get access to placement support with leading prop trading firms and financial institutions.",
            "icon": "Trophy"
        }
    ],
    "leadership": [
        {
            "name": "Het Vyas",
            "title": "Founder & COO",
            "monogram": "HV",
            "headerDetail": "📈 ₹50 Cr+ Live Market Experience",
            "stats": [
                { "value": "₹50 Cr+", "label": "Market Experience" },
                { "value": "Prop Trading", "label": "Platform" },
                { "value": "Forex • Equity • Derivatives", "label": "Expertise" }
            ],
            "bio": "EdTech entrepreneur and Founder of The FinTrade, India's first structured prop trading academy and capital allocation platform. He built a full-stack ecosystem to bridge trading education with real income opportunities for retail traders, students, and professionals. With ₹50 Cr+ in live market experience across Forex, equity, and derivatives, he founded The FinTrade to address the 95% trader failure rate caused by gaps in traditional education systems.",
            "tags": [
                "₹50 Cr+ Live Market Experience",
                "Forex, Equity & Derivatives",
                "EdTech Entrepreneur",
                "India's First Prop Trading Academy"
            ]
        },
        {
            "name": "Chirag Panchal",
            "title": "Managing Director & CEO",
            "monogram": "CP",
            "headerDetail": "💼 22+ Years Media Leadership",
            "stats": [
                { "value": "22+ Years", "label": "Leadership" },
                { "value": "5 Media", "label": "Platforms Built" },
                { "value": "Strategy & Growth", "label": "Expertise" }
            ],
            "bio": "Media strategist and entrepreneur with 22+ years of leadership experience in the Gujarati media industry. He has successfully built and scaled platforms such as TV9 Gujarati, GSTV, Zee 24 Kalak, TV13 Gujarati, and News Capital, combining strong strategic vision with execution excellence. With expertise in content, marketing, and revenue growth, he specializes in market positioning, audience engagement, growth strategy, end-to-end project execution, and team leadership.",
            "tags": [
                "22+ Years Media Leadership",
                "TV9 Gujarati, GSTV, Zee 24 Kalak",
                "Market Positioning Expert",
                "Growth Strategy & Execution"
            ]
        },
        {
            "name": "Bhargav Dave",
            "title": "VP, Training & Development",
            "monogram": "BD",
            "headerDetail": "🪙 ₹25 Cr+ Capital Managed",
            "stats": [
                { "value": "20+ Years", "label": "Experience" },
                { "value": "₹25 Cr+", "label": "Capital Managed" },
                { "value": "250+", "label": "Traders Trained" }
            ],
            "bio": "Highly respected capital market professional with 20+ years of expertise in proprietary trading, derivatives strategies, investment advisory, and financial market education. As Assistant Vice President at Junomoneta Finsol Pvt Ltd, he has successfully managed ₹25+ crore in trading capital while leading and mentoring a team of professional traders. Known for his sharp market insight, disciplined risk management, and strategic execution, Bhargav has trained 250+ traders and delivered 150+ institutional programs through reputed platforms including NISM and NSE Academy.",
            "tags": [
                "₹25 Cr+ Capital Managed",
                "250+ Traders Trained",
                "150+ Institutional Programs",
                "NISM & NSE Academy"
            ]
        }
    ]
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
        data = json.loads(setting.value)
        if not isinstance(data, dict):
            return DEFAULT_LANDING_PAGE_CONFIG
        if "benefits" not in data:
            data["benefits"] = DEFAULT_LANDING_PAGE_CONFIG["benefits"]
        if "services" not in data:
            data["services"] = DEFAULT_LANDING_PAGE_CONFIG["services"]
        if "quick_tips" not in data:
            data["quick_tips"] = DEFAULT_LANDING_PAGE_CONFIG["quick_tips"]
        if "why_choose" not in data:
            data["why_choose"] = DEFAULT_LANDING_PAGE_CONFIG["why_choose"]
        if "leadership" not in data:
            data["leadership"] = DEFAULT_LANDING_PAGE_CONFIG["leadership"]
        return data
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
