"""Exams module — Pydantic schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Admin: Create exam / question / option ──────────────────────────
class ExamOptionCreate(BaseModel):
    option_text: str = Field(..., min_length=1)
    is_correct: bool = False
    order: int = 0


class ExamQuestionCreate(BaseModel):
    question_text: str = Field(..., min_length=1)
    question_type: str = "mcq"  # mcq, true_false, multi_select, descriptive
    marks: float = 1.0
    negative_marks: float = 0.0
    order: int = 0
    category: Optional[str] = None
    explanation: Optional[str] = None
    options: List[ExamOptionCreate] = []


class EntranceExamCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    course_id: int
    duration_minutes: int = 60
    passing_score: float = 60.0
    is_active: bool = True
    max_attempts: int = 3
    fee: float = 0.0
    cooldown_days: int = 0
    questions_per_attempt: Optional[int] = None  # null = use all questions
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: List[ExamQuestionCreate] = []

class CourseExamCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    course_id: int
    module_id: Optional[int] = None
    exam_type: str = "course_final"
    duration_minutes: int = 60
    passing_score: float = 60.0
    max_attempts: int = 3
    is_active: bool = True
    questions_per_attempt: Optional[int] = None  # null = use all questions
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: List[ExamQuestionCreate] = []

class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    passing_score: Optional[float] = None
    is_active: Optional[bool] = None


# ── Response schemas ─────────────────────────────────────────────────
class ExamOptionResponse(BaseModel):
    id: int
    option_text: str
    order: int
    # NOTE: is_correct is intentionally excluded for students

    model_config = {"from_attributes": True}


class ExamQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_type: str
    marks: float
    negative_marks: float
    order: int
    category: Optional[str] = None
    options: List[ExamOptionResponse] = []

    model_config = {"from_attributes": True}


class EntranceExamResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_id: int
    duration_minutes: int
    passing_score: float
    max_attempts: int = 3
    is_active: bool
    fee: float = 0.0
    cooldown_days: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttemptStartResponse(BaseModel):
    attempt_id: int
    exam_id: int
    started_at: datetime
    duration_minutes: int
    total_questions: int

    model_config = {"from_attributes": True}


# ── Answer submission ────────────────────────────────────────────────
class AnswerSubmit(BaseModel):
    question_id: int
    selected_option_id: Optional[int] = None
    descriptive_text: Optional[str] = None


class ExamSubmitRequest(BaseModel):
    attempt_id: int
    answers: List[AnswerSubmit] = []


# ── Result ───────────────────────────────────────────────────────────
class ExamResultResponse(BaseModel):
    id: int
    attempt_id: int
    total_questions: int
    correct_answers: int
    total_marks: float
    obtained_marks: float
    percentage: float
    passed: bool
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


# ── Phase 2 Schemas ───────────────────────────────────────────────────

class EntranceExamPaymentRequest(BaseModel):
    entrance_exam_id: int
    amount: float = 50.0

class EntranceExamPaymentResponse(BaseModel):
    id: int
    entrance_exam_id: int
    amount: float
    status: str
    is_used: bool

    model_config = {"from_attributes": True}


class CourseExamResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    course_id: int
    module_id: Optional[int] = None
    exam_type: str
    duration_minutes: int
    passing_score: float
    max_attempts: int
    is_active: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    model_config = {"from_attributes": True}

class MonthlyExamResponse(BaseModel):
    id: int
    course_id: int
    month_number: int
    exam: Optional[CourseExamResponse] = None

    model_config = {"from_attributes": True}

class ExamStartRequest(BaseModel):
    device_id: str

class AttemptCourseStartResponse(BaseModel):
    attempt_id: int
    exam_id: int
    started_at: datetime
    duration_minutes: int
    device_id: Optional[str] = None

    model_config = {"from_attributes": True}

class ExamPaymentRequest(BaseModel):
    exam_id: int
    amount: float = 50.0

class ExamViolationRequest(BaseModel):
    attempt_id: int
    violation_type: str

class CameraStatusRequest(BaseModel):
    attempt_id: int
    camera_on: bool

class SessionCloseRequest(BaseModel):
    attempt_id: int


# ── Exam Results & Reviews ───────────────────────────────────────────

class ExamOptionReview(BaseModel):
    id: int
    option_text: str
    is_correct: bool

    model_config = {"from_attributes": True}

class QuestionReview(BaseModel):
    id: int
    question_text: str
    question_type: str
    marks: float
    negative_marks: float
    explanation: Optional[str] = None
    options: List[ExamOptionReview] = []
    selected_option_id: Optional[int] = None
    is_correct: Optional[bool] = None

class AttemptReviewResponse(BaseModel):
    attempt_id: int
    exam_title: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    total_questions: int
    correct_answers: int
    total_marks: float
    obtained_marks: float
    percentage: float
    passed: bool
    violations: List[str] = []
    questions: List[QuestionReview] = []

    model_config = {"from_attributes": True}

class AttemptSummary(BaseModel):
    id: int
    submitted_at: Optional[datetime] = None
    percentage: float = 0.0
    passed: bool = False
    is_violation_wasted: bool = False

    model_config = {"from_attributes": True}

# ── Skill Analysis ───────────────────────────────────────────────────

class CategoryScoreResponse(BaseModel):
    category: str
    score: float
    max_score: float
    percentage: float

    model_config = {"from_attributes": True}


class SkillAnalysisResponse(BaseModel):
    strong_areas: list[CategoryScoreResponse]
    weak_areas: list[CategoryScoreResponse]
    suggestions: list[str]

