import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.base import import_all_models
from app.modules.franchise_ibs.models import FranchiseIB
from app.modules.auth.models import User

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(FranchiseIB))
        ibs = result.scalars().all()
        print(f"Found {len(ibs)} franchise IBs.")
        for ib in ibs:
            user = await db.get(User, ib.user_id)
            await db.delete(ib)
            if user:
                await db.delete(user)
                print(f"Deleted IB and user {user.email}")
            else:
                await db.delete(ib)
                print(f"Deleted IB {ib.id} with no user")
        await db.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
