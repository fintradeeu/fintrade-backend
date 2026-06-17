import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from sqlalchemy import select
from app.modules.auth.models import User
from app.core.security import hash_password

async def main():
    async with AsyncSessionLocal() as session:
        res_user = await session.execute(select(User).where(User.email == "sujalgujar0@gmail.com"))
        user = res_user.scalar_one_or_none()
        if not user:
            print("Student user sujalgujar0@gmail.com not found!")
            return

        user.hashed_password = hash_password("student123")
        user.is_active = True
        user.is_verified = True
        await session.commit()
        print(f"Successfully updated password for {user.email} to 'student123'!")

if __name__ == "__main__":
    asyncio.run(main())
