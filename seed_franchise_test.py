import asyncio
from app.db.database import AsyncSessionLocal
from app.modules.auth.models import User, Role
from app.modules.franchise_ibs.models import FranchiseIB
from passlib.context import CryptContext
import traceback
import app.modules.courses.models
import app.modules.distributors.models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_test_franchise():
    async with AsyncSessionLocal() as db:
        try:
            # Check if role exists
            from sqlalchemy import select
            result = await db.execute(select(Role).where(Role.name == "franchise_ib"))
            role = result.scalar_one_or_none()
            if not role:
                print("franchise_ib role not found! Creating it...")
                role = Role(name="franchise_ib", description="Franchise IB Role")
                db.add(role)
                await db.flush()

            email = "test.franchise@fintrade.com"
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"Test user {email} already exists!")
                return
            
            print("Creating test Franchise IB user...")
            new_user = User(
                full_name="Test Franchise Account",
                email=email,
                phone="9999999999",
                hashed_password=pwd_context.hash("password123"),
                roles=[role],
                is_active=True
            )
            db.add(new_user)
            await db.flush()
            
            print("Creating Franchise IB Profile...")
            new_profile = FranchiseIB(
                user_id=new_user.id,
                referral_code="FIB-TEST-123",
                pan_number="ABCDE1234F",
                verification_status="approved"
            )
            db.add(new_profile)
            await db.commit()
            
            print("Successfully created Franchise IB Test Account!")
            print(f"Email: {email}")
            print(f"Password: password123")
            
        except Exception as e:
            await db.rollback()
            print("Error occurred:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(seed_test_franchise())
