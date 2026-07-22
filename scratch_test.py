import asyncio
import sys
import traceback
import uuid

sys.path.append(".")

from app.db.database import AsyncSessionLocal
from app.modules.distributors.schemas import ManualStudentRegisterRequest
from app.modules.distributors.services import manual_register_student
from app.modules.franchise_ibs.models import FranchiseIB
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        try:
            # Query the seeded FranchiseIB profile
            result = await db.execute(select(FranchiseIB).where(FranchiseIB.referral_code == "FIB-TEST-123"))
            profile = result.scalar_one_or_none()
            if not profile:
                print("Seeded FranchiseIB profile not found!")
                return
            
            print(f"Found FranchiseIB profile! ID: {profile.id}")

            unique_suffix = uuid.uuid4().hex[:6]
            req = ManualStudentRegisterRequest(
                full_name="Test Student",
                email=f"test_student_{unique_suffix}@gmail.com",
                password="password123",
                phone=f"9900{uuid.uuid4().hex[:6]}",
                city="Ahmedabad",
                course_id=1,
                batch_id=1,
                payment_mode="cash",
                amount=1000.0,
                reference_number=f"CASH-{unique_suffix}"
            )
            res = await manual_register_student(db, req, franchise_ib_id=profile.id)
            print("SUCCESS:", res)
        except Exception as e:
            print("ERROR:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
