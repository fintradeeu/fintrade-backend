import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
import app.main
from app.modules.courses.models import CourseEnrollment
from app.modules.payments.models import PaymentTransaction
from app.modules.admin.services import list_purchased_students

async def main():
    async with AsyncSessionLocal() as db:
        print('Fetching enrolled students...')
        data = await list_purchased_students(db, limit=1000)
        users = data['users']
        users_to_delete = [
            u for u in users
            if not any(role.name == 'distributor' for role in u.roles)
        ]
        
        print(f'Found {len(users_to_delete)} purchased students to delete.')
        
        for u in users_to_delete:
            print(f'Deleting user: {u.full_name} ({u.email})')
            
            # delete payment transactions
            txs = await db.execute(select(PaymentTransaction).where(PaymentTransaction.user_id == u.id))
            for tx in txs.scalars().all():
                await db.delete(tx)
            
            # delete enrollments
            enrs = await db.execute(select(CourseEnrollment).where(CourseEnrollment.user_id == u.id))
            for e in enrs.scalars().all():
                await db.delete(e)
            
            # delete user
            await db.delete(u)
            
        await db.commit()
        print('Deletion complete.')

if __name__ == '__main__':
    asyncio.run(main())
