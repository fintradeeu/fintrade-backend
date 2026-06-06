"""Faculty module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.courses.schemas import LessonCreate, LessonResponse, CourseListResponse
from app.modules.lectures.schemas import LectureCreate, LectureResponse


class FacultyStudentResponse(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    course_id: int
    course_title: str
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str

class TrendData(BaseModel):
    month: str
    avgScore: int
    passRate: int

class TopicData(BaseModel):
    topic: str
    struggles: int

class ModuleData(BaseModel):
    module: str
    completion: int

class DistributionData(BaseModel):
    category: str
    value: int

class StudentProgressDetail(BaseModel):
    student_name: str
    student_email: str
    course_title: str
    enrolled_at: datetime
    progress_percent: float

class ExamScoreDetail(BaseModel):
    student_name: str
    exam_title: str
    course_title: str
    obtained_marks: float
    total_marks: float
    percentage: float
    passed: bool
    evaluated_at: datetime

class AssignmentSubmissionDetail(BaseModel):
    student_name: str
    assignment_title: str
    course_title: str
    status: str
    score: Optional[float] = None
    submitted_at: datetime

class FacultyReportsResponse(BaseModel):
    avg_class_score: int
    pass_rate: int
    completion_rate: int
    at_risk_students: int
    performance_trend: List[TrendData]
    weak_topics: List[TopicData]
    module_completion: List[ModuleData]
    student_distribution: List[DistributionData]
    student_progress: List[StudentProgressDetail] = []
    exam_scores: List[ExamScoreDetail] = []
    assignment_submissions: List[AssignmentSubmissionDetail] = []
#Faculty
# Temp line for commit trigger

class StudentEnrolledCourseDetail(BaseModel):
    course_id: int
    title: str
    enrolled_at: datetime
    completed_at: Optional[datetime]
    progress_percent: float

class StudentAssignmentDetail(BaseModel):
    assignment_id: int
    title: str
    course_id: int
    course_title: str
    submitted_at: datetime
    status: str
    score: Optional[float]
    max_score: float
    file_url: str
    teacher_feedback: Optional[str]

class ExamAnswerDetail(BaseModel):
    question_text: str
    question_type: str
    marks: float
    correct_option: Optional[str]
    selected_option: Optional[str]
    is_correct: Optional[bool]

class StudentExamDetail(BaseModel):
    exam_id: int
    title: str
    exam_type: str
    course_title: Optional[str]
    score: float
    total_marks: float
    passed: bool
    submitted_at: Optional[datetime]
    answers: List[ExamAnswerDetail]

class StudentProfileResponse(BaseModel):
    student_id: int
    name: str
    email: str
    courses: List[StudentEnrolledCourseDetail]
    assignments: List[StudentAssignmentDetail]
    exams: List[StudentExamDetail]