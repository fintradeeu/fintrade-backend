"""Batches module — validation and API schemas."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, model_validator


class BatchBase(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    registration_start_date: datetime
    registration_end_date: datetime
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    max_students: Optional[int] = 100
    is_published: Optional[bool] = False
    is_active: Optional[bool] = True


class BatchCreate(BatchBase):
    copy_from_batch_id: Optional[int] = None  # If provided, system will deep-copy from this batch


class BatchUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    registration_start_date: Optional[datetime] = None
    registration_end_date: Optional[datetime] = None
    status: Optional[str] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    max_students: Optional[int] = None
    is_published: Optional[bool] = None
    is_active: Optional[bool] = None


class BatchCourseAssign(BaseModel):
    course_ids: List[int]


class BatchOnlyCourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    difficulty_level: Optional[str] = "beginner"
    duration_hours: Optional[int] = None


class BatchResponse(BatchBase):
    id: int
    batch_code: str
    status: str
    current_students: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    assigned_courses: List[dict] = []

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def serialize_courses(cls, data):
        # Handle ORM model
        if hasattr(data, "courses") and data.courses:
            assigned = []
            for bc in data.courses:
                if bc.course:
                    assigned.append({
                        "id": bc.course.id,
                        "title": bc.course.title,
                        "price": bc.course.price,
                        "is_batch_only": bool(getattr(bc.course, "is_batch_only", False)),
                    })
            # Inject
            if isinstance(data, dict):
                data["assigned_courses"] = assigned
            else:
                setattr(data, "assigned_courses", assigned)
        return data


class BatchListResponse(BaseModel):
    batches: List[BatchResponse]
    total: int


class StudentResponse(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    enrolled_at: datetime
    course_id: Optional[int] = None
    course_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BatchDashboardResponse(BaseModel):
    batch_id: int
    name: str
    batch_code: str
    status: str
    start_date: datetime
    end_date: datetime
    countdown_seconds: int  # Seconds until start_date (0 if already started)
    is_locked: bool         # True if now < start_date
    assigned_courses: List[dict]
    progress_percent: float

    model_config = ConfigDict(from_attributes=True)


class BatchModuleCreate(BaseModel):
    batch_id: int
    course_id: int
    title: str
    description: Optional[str] = None
    order: Optional[int] = 0
    is_published: Optional[bool] = False


class BatchModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    is_published: Optional[bool] = None


class BatchLessonCreate(BaseModel):
    batch_module_id: int
    title: str
    content: Optional[str] = None
    content_type: Optional[str] = "text"
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order: Optional[int] = 0
    is_published: Optional[bool] = False


class BatchLessonUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order: Optional[int] = None
    is_published: Optional[bool] = None


class BatchLessonResponse(BaseModel):
    id: int
    batch_module_id: int
    template_lesson_id: Optional[int] = None
    title: str
    content: Optional[str] = None
    content_type: str
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order: int
    is_published: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchModuleResponse(BaseModel):
    id: int
    batch_id: int
    course_id: int
    template_module_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    order: int
    is_published: bool
    lessons: List[BatchLessonResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchLectureCreate(BaseModel):
    batch_id: int
    course_id: int
    title: str
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: Optional[int] = 60
    is_live: Optional[bool] = False
    is_completed: Optional[bool] = False
    instructor_name: Optional[str] = None
    end_time: Optional[datetime] = None


class BatchLectureUpdate(BaseModel):
    course_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    is_live: Optional[bool] = None
    is_completed: Optional[bool] = None
    instructor_name: Optional[str] = None
    end_time: Optional[datetime] = None


class BatchLectureResponse(BaseModel):
    id: int
    batch_id: int
    course_id: int
    title: str
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    is_live: bool
    is_completed: bool
    instructor_name: Optional[str] = None
    end_time: Optional[datetime] = None
    max_participants: int = 0
    recordings: List[dict] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchAssignmentCreate(BaseModel):
    batch_id: int
    course_id: int
    batch_module_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_score: Optional[float] = 100.0
    resources: Optional[List[dict[str, Any]]] = None


class BatchAssignmentUpdate(BaseModel):
    course_id: Optional[int] = None
    batch_module_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_score: Optional[float] = None
    resources: Optional[List[dict[str, Any]]] = None


class BatchAssignmentResponse(BaseModel):
    id: int
    batch_id: int
    course_id: int
    batch_module_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_score: float
    resources: Optional[List[dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchAssignmentSubmissionCreate(BaseModel):
    batch_assignment_id: int
    file_url: str


class BatchAssignmentSubmissionResponse(BaseModel):
    id: int
    batch_assignment_id: int
    assignment_id: int = 0
    user_id: int
    file_url: str
    submitted_at: datetime
    status: str
    score: Optional[float] = None
    teacher_feedback: Optional[str] = None
    user: Optional[StudentResponse] = None

    model_config = ConfigDict(from_attributes=True)


class BatchDayTaskCreate(BaseModel):
    batch_id: Optional[int] = None
    course_id: int
    day_number: int
    title: str
    content_type: Optional[str] = "text"
    content: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_published: Optional[bool] = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    instructor_name: Optional[str] = None
    exam_title: Optional[str] = None
    exam_passing_score: Optional[float] = None
    linked_assignment_id: Optional[int] = None


class BatchDayTaskUpdate(BaseModel):
    day_number: Optional[int] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_published: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    instructor_name: Optional[str] = None
    exam_title: Optional[str] = None
    exam_passing_score: Optional[float] = None
    linked_assignment_id: Optional[int] = None


class BatchDayTaskResponse(BaseModel):
    id: int
    batch_id: Optional[int] = None
    course_id: int
    day_number: int
    title: str
    content_type: str
    content: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_published: bool
    created_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    instructor_name: Optional[str] = None
    exam_title: Optional[str] = None
    exam_passing_score: Optional[float] = None
    linked_assignment_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def serialize_assignment_id(cls, data):
        if hasattr(data, "batch_assignment_id"):
            setattr(data, "assignment_id", data.batch_assignment_id)
        elif isinstance(data, dict) and "batch_assignment_id" in data:
            data["assignment_id"] = data["batch_assignment_id"]
        return data
