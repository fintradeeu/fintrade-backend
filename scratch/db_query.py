import asyncio
import sys
from sqlalchemy import select

# Add parent dir to path
sys.path.append(".")

from app.db.database import AsyncSessionLocal
from app.modules.settings.models import PlatformSetting

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(PlatformSetting))
        settings = res.scalars().all()
        print(f"Total settings found: {len(settings)}")
        for s in settings:
            print(f"Key: {s.key} | Category: {s.category} | Value: {s.value[:200] if s.value else None}")

if __name__ == '__main__':
    asyncio.run(main())
