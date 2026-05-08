"""Async SQLAlchemy database engine and session management."""

import ssl
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _build_engine():
    """Build the async engine with SSL if needed (Neon / Vercel Postgres)."""
    url = settings.async_database_url

    connect_args = {}

    # Neon / Vercel Postgres require SSL
    if "neon.tech" in url or "vercel-storage" in url:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    # Strip sslmode from URL — asyncpg doesn't understand it as a query param
    if "sslmode=" in url:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        cleaned_query = urlencode(params, doseq=True)
        url = urlunparse(parsed._replace(query=cleaned_query))

    return create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=3,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


engine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def get_db():
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create tables (development convenience — use Alembic in production)."""
    async with engine.begin() as conn:
        from app.db.base import import_all_models  # noqa
        await conn.run_sync(Base.metadata.create_all)

