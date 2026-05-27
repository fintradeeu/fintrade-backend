"""Learning module — services."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from sqlalchemy import func

from app.modules.learning.models import LessonCompletion
from app.modules.courses.models import CourseEnrollment, Course, CourseModule, Lesson
from app.modules.lectures.models import Lecture
from app.modules.learning.schemas import LearningDashboardResponse, EnrolledCourseProgress, CompletedLessonItem, UpcomingLectureItem, VideoPolicyItem

async def get_user_dashboard(db: AsyncSession, user_id: int) -> LearningDashboardResponse:
    # 1. Enrolled Courses
    enrollment_stmt = select(CourseEnrollment).options(
        selectinload(CourseEnrollment.course)
    ).where(CourseEnrollment.user_id == user_id, CourseEnrollment.is_active == True)
    
    enrollment_result = await db.execute(enrollment_stmt)
    enrollments = enrollment_result.scalars().all()
    
    enrolled_courses = [
        EnrolledCourseProgress(
            course_id=e.course_id,
            title=e.course.title,
            thumbnail_url=e.course.thumbnail_url,
            progress_percent=e.progress_percent,
            enrolled_at=e.enrolled_at,
        ) for e in enrollments
    ]
    
    # 2. Completed Lessons
    completion_stmt = select(LessonCompletion, Lesson.title).join(
        Lesson, LessonCompletion.lesson_id == Lesson.id
    ).where(LessonCompletion.user_id == user_id)
    
    completion_result = await db.execute(completion_stmt)
    completions = completion_result.all()
    
    completed_lessons = [
        CompletedLessonItem(
            lesson_id=row[0].lesson_id,
            title=row[1],
            completed_at=row[0].completed_at
        ) for row in completions
    ]
    
    # 3. Upcoming Lectures mapping to enrolled courses
    course_ids = [e.course_id for e in enrollments]
    upcoming_lectures = []
    if course_ids:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        lectures_stmt = select(Lecture).where(
            Lecture.course_id.in_(course_ids),
            Lecture.scheduled_at > now,
            Lecture.is_live == True
        ).order_by(Lecture.scheduled_at).limit(5)
        
        lectures_result = await db.execute(lectures_stmt)
        lectures = lectures_result.scalars().all()
        
        upcoming_lectures = [
            UpcomingLectureItem(
                id=l.id,
                title=l.title,
                start_time=l.scheduled_at,
                topic=l.description or l.title
            ) for l in lectures
        ]

    # 4. Video Policies
    from app.modules.courses.models import ModuleStudentPolicy
    policy_stmt = select(ModuleStudentPolicy).where(ModuleStudentPolicy.student_id == user_id)
    policy_result = await db.execute(policy_stmt)
    policies = policy_result.scalars().all()
    
    video_policies = [
        VideoPolicyItem(
            module_id=p.module_id,
            mandatory=p.mandatory
        ) for p in policies
    ]
        
    return LearningDashboardResponse(
        enrolled_courses=enrolled_courses,
        completed_lessons=completed_lessons,
        upcoming_lectures=upcoming_lectures,
        video_policies=video_policies
    )


async def mark_lesson_completed(db: AsyncSession, user_id: int, course_id: int, lesson_id: int) -> bool:
    # Check if already completed
    check_stmt = select(LessonCompletion).where(
        LessonCompletion.user_id == user_id,
        LessonCompletion.lesson_id == lesson_id
    )
    res = await db.execute(check_stmt)
    if res.scalar_one_or_none():
        return True # already completed
        
    new_completion = LessonCompletion(
        user_id=user_id,
        lesson_id=lesson_id,
        course_id=course_id
    )
    db.add(new_completion)
    
    # Optionally update course progress percent
    # Real calc: count(completed) / count(total) * 100
    enroll_stmt = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id == course_id
    )
    enroll_res = await db.execute(enroll_stmt)
    enrollment = enroll_res.scalar_one_or_none()
    
    if enrollment:
        # Real calculation: count completed lessons / total published lessons
        total_lessons_stmt = (
            select(func.count(Lesson.id))
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .where(CourseModule.course_id == course_id, Lesson.is_published == True)
        )
        total_res = await db.execute(total_lessons_stmt)
        total_lessons = total_res.scalar() or 1

        completed_stmt = select(func.count(LessonCompletion.id)).where(
            LessonCompletion.user_id == user_id,
            LessonCompletion.course_id == course_id,
        )
        completed_res = await db.execute(completed_stmt)
        completed_count = completed_res.scalar() or 0

        enrollment.progress_percent = round((completed_count / total_lessons) * 100, 2)

        if enrollment.progress_percent >= 100.0:
            enrollment.progress_percent = 100.0
            if not enrollment.completed_at:
                from datetime import datetime, timezone
                enrollment.completed_at = datetime.now(timezone.utc)
    
    await db.commit()
    return True
