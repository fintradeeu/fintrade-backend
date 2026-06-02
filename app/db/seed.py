"""Database seed script — creates default roles and admin user."""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import AsyncSessionLocal, init_db
from app.modules.auth.models import Role, User
from app.core.security import hash_password
from app.config import settings
from sqlalchemy import select


ROLES = ["super_admin", "admin", "faculty", "student", "distributor"]

DEFAULT_ADMIN = {
    "email": settings.ADMIN_EMAIL,
    "full_name": settings.ADMIN_FULL_NAME,
    "password": settings.ADMIN_PASSWORD,
}


async def seed(skip_init_db: bool = False):
    """Seed the database with default roles and admin account."""
    # Ensure tables exist (skip if caller already did this)
    if not skip_init_db:
        await init_db()

    async with AsyncSessionLocal() as db:
        try:
            # Create roles
            for role_name in ROLES:
                result = await db.execute(select(Role).where(Role.name == role_name))
                if result.scalar_one_or_none() is None:
                    db.add(Role(name=role_name, description=f"{role_name.capitalize()} role"))
                    print(f"  ✓ Created role: {role_name}")
                else:
                    print(f"  · Role already exists: {role_name}")

            await db.flush()

            # Create default admin
            result = await db.execute(
                select(User).where(User.email == DEFAULT_ADMIN["email"])
            )
            admin = result.scalar_one_or_none()

            if admin is None:
                # Get admin role
                role_result = await db.execute(select(Role).where(Role.name == "admin"))
                admin_role = role_result.scalar_one()

                admin = User(
                    email=DEFAULT_ADMIN["email"],
                    full_name=DEFAULT_ADMIN["full_name"],
                    hashed_password=hash_password(DEFAULT_ADMIN["password"]),
                    is_active=True,
                    is_verified=True,
                )
                admin.roles.append(admin_role)
                db.add(admin)
                await db.flush()
                print(f"  ✓ Created admin: {DEFAULT_ADMIN['email']} (password: {DEFAULT_ADMIN['password']})")
            else:
                print(f"  · Admin already exists: {DEFAULT_ADMIN['email']}")

            await db.commit()
            print("\n✅ Seed completed successfully!")

        except Exception as e:
            await db.rollback()
            print(f"\n❌ Seed failed: {e}")
            raise


if __name__ == "__main__":
    print("🌱 Seeding database...\n")
    asyncio.run(seed())
