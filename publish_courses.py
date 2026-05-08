import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://lms_user:lms_password@localhost:5432/lms_db")
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE courses SET is_published = TRUE;"))
    print("All courses have been set to published!")

if __name__ == "__main__":
    asyncio.run(main())
