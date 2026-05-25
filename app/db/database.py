"""Async SQLAlchemy database engine and session management."""

import asyncio
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def get_engine_args():
    """Build the async engine args with SSL if needed (Neon / Vercel Postgres)."""
    url = settings.async_database_url
    connect_args = {}

    # Hosted Postgres providers commonly require SSL.
    if "render.com" in url:
        connect_args["ssl"] = True
    elif "neon.tech" in url or "vercel-storage" in url:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    return {
        "url": url,
        "echo": settings.DEBUG,
        "pool_size": 5,
        "max_overflow": 3,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": connect_args,
    }

engine = create_async_engine(**get_engine_args())

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


async def init_db():
    """Create tables with a short retry window for local Postgres startup."""
    last_error = None
    for attempt in range(1, 6):
        try:
            async with engine.begin() as conn:
                from app.db.base import import_all_models  # noqa
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as exc:
            last_error = exc
            if attempt == 5:
                break
            await asyncio.sleep(attempt)
    raise last_error

