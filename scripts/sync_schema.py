"""Run on every deploy — creates any missing tables from SQLAlchemy models."""
import asyncio
from app.db.database import Base, engine
from app.main import app  # imports all models via routers

async def sync():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Schema sync done')

asyncio.run(sync())
