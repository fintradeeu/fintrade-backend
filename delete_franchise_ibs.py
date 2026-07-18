import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import async_session_maker
from app.modules.auth.models import User, Role
from sqlalchemy import select

async def main():
    async with async_session_maker() as db:
        result = await db.execute(select(User).join(User.roles).where(Role.name == 'franchise_ib'))
        users = result.scalars().all()
        for u in users:
            print("Deleting Franchise IB:", u.id, u.email, u.full_name)
            await db.delete(u)
        await db.commit()
        print("Done deleting Franchise IBs.")

if __name__ == '__main__':
    asyncio.run(main())
