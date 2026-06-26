import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from sqlalchemy import select
from app.modules.auth.models import User
from app.modules.courses.models import Course, CourseEnrollment
from app.modules.distributors.models import Distributor # Needed to register distributors table for relationship resolution

async def main():
    async with AsyncSessionLocal() as session:
        # Get student user
        res_user = await session.execute(select(User).where(User.email == "sujalgujar0@gmail.com"))
        user = res_user.scalar_one_or_none()
        if not user:
            print("Student user sujalgujar0@gmail.com not found!")
            return

        # Get course
        res_course = await session.execute(select(Course).where(Course.id == 1))
        course = res_course.scalar_one_or_none()
        if not course:
            print("Course ID 1 not found!")
            return

        # Check if enrollment already exists
        res_enroll = await session.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == user.id,
                CourseEnrollment.course_id == course.id
            )
        )
        enrollment = res_enroll.scalar_one_or_none()
        if enrollment:
            print("Enrollment already exists!")
            return

        # Create enrollment
        new_enrollment = CourseEnrollment(
            user_id=user.id,
            course_id=course.id,
            is_active=True,
            progress_percent=0.0
        )
        session.add(new_enrollment)
        await session.commit()
        print(f"Successfully enrolled {user.email} in course '{course.title}'!")

if __name__ == "__main__":
    asyncio.run(main())
