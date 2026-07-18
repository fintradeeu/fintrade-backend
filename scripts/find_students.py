import asyncio
# pyrefly: ignore [missing-import]
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.modules.auth.models import User
from app.modules.distributors.models import StudentReferral
from app.modules.courses.models import CourseEnrollment
from app.db.base import import_all_models

async def main():
    async with AsyncSessionLocal() as db:
        # Find the franchise user
        result = await db.execute(select(User).where(User.full_name.ilike('%bansi%')))
        users = result.scalars().all()
        for u in users:
            print(f"Franchise user candidate: id={u.id}, name={u.full_name}, email={u.email}")
            
        # Find the students
        result = await db.execute(select(User).where(User.full_name.in_(['sujal gujar', 'mahesh mali'])))
        students = result.scalars().all()
        for s in students:
            print(f"Student candidate: id={s.id}, name={s.full_name}, email={s.email}")

if __name__ == "__main__":
    asyncio.run(main())
