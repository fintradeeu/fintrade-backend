"""Learning module — schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class EnrolledCourseProgress(BaseModel):
    course_id: int
    title: str
    thumbnail_url: Optional[str]
    progress_percent: float
    enrolled_at: datetime
    
    class Config:
        from_attributes = True


class CompletedLessonItem(BaseModel):
    lesson_id: int
    title: str
    completed_at: datetime
    
    class Config:
        from_attributes = True


class UpcomingLectureItem(BaseModel):
    id: int
    title: str
    start_time: datetime
    topic: str
    
    class Config:
        from_attributes = True


class VideoPolicyItem(BaseModel):
    module_id: int
    mandatory: bool

    class Config:
        from_attributes = True


class LearningDashboardResponse(BaseModel):
    enrolled_courses: List[EnrolledCourseProgress]
    completed_lessons: List[CompletedLessonItem]
    upcoming_lectures: List[UpcomingLectureItem]
    video_policies: List[VideoPolicyItem] = []

class MarkLessonCompletedRequest(BaseModel):
    course_id: int
    lesson_id: int

