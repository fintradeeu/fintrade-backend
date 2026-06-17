import asyncio
import os
import sys

from app.db.database import AsyncSessionLocal
from app.modules.courses.models import Course, CourseModule, Lesson
from app.modules.exams.models import EntranceExam, ExamQuestion, ExamOption
from app.modules.auth.models import User

async def seed_data():
    async with AsyncSessionLocal() as db:
        # Check if dummy data already exists
        # Fetch first admin to associate created courses
        # Wait, get admin
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == "admin@platform.com"))
        admin = result.scalar_one_or_none()
        admin_id = admin.id if admin else None

        c_result = await db.execute(select(Course).where(Course.title == "Demo Technical Analysis"))
        c_exist = c_result.scalar_one_or_none()
        
        if c_exist:
            print("Demo data already seeded.")
            return

        print("Seeding Demo Technical Analysis Course...")
        course1 = Course(
            title="Demo Technical Analysis",
            slug="demo-tech-analysis",
            description="A comprehensive demo course on technical analysis.",
            short_description="Learn TA basics.",
            price=4999.0,
            is_published=True,
            difficulty_level="beginner",
            duration_hours=10,
            created_by=admin_id
        )
        db.add(course1)
        await db.flush()

        mod1 = CourseModule(
            course_id=course1.id,
            title="Module 1: Introduction",
            description="Introduction to candlesticks",
            order=1,
            is_published=True
        )
        db.add(mod1)
        await db.flush()

        les1 = Lesson(
            module_id=mod1.id,
            title="Candlestick Basics",
            content_type="video",
            video_url="https://www.w3schools.com/html/mov_bbb.mp4",
            duration_minutes=15,
            order=1,
            is_published=True
        )
        les2 = Lesson(
            module_id=mod1.id,
            title="Reading Patterns",
            content_type="text",
            content="This is a text lesson on reading patterns like Doji and Hammer.",
            duration_minutes=10,
            order=2,
            is_published=True
        )
        db.add_all([les1, les2])
        await db.flush()

        print("Seeding Entrance Exam for Demo Course...")
        exam = EntranceExam(
            title="TA Basics Entrance Exam",
            description="Take this test to evaluate your basics.",
            course_id=course1.id,
            duration_minutes=30,
            passing_score=50.0,
            is_active=True
        )
        db.add(exam)
        await db.flush()

        q1 = ExamQuestion(
            exam_id=exam.id,
            question_text="What does a Doji candlestick indicate?",
            question_type="mcq",
            marks=10.0,
            order=1
        )
        q2 = ExamQuestion(
            exam_id=exam.id,
            question_text="Which of these is a bullish reversal pattern?",
            question_type="mcq",
            marks=10.0,
            order=2
        )
        db.add_all([q1, q2])
        await db.flush()

        # Add options for q1
        db.add_all([
            ExamOption(question_id=q1.id, option_text="Indecision in the market", is_correct=True, order=1),
            ExamOption(question_id=q1.id, option_text="Strong uptrend", is_correct=False, order=2),
            ExamOption(question_id=q1.id, option_text="Strong downtrend", is_correct=False, order=3),
        ])

        # Add options for q2
        db.add_all([
            ExamOption(question_id=q2.id, option_text="Hammer", is_correct=True, order=1),
            ExamOption(question_id=q2.id, option_text="Shooting Star", is_correct=False, order=2),
            ExamOption(question_id=q2.id, option_text="Bearish Engulfing", is_correct=False, order=3),
        ])

        await db.commit()
        print("Demo data successfully seeded!")

if __name__ == "__main__":
    asyncio.run(seed_data())
