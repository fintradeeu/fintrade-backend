"""Exams module — database models for entrance exams."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class EntranceExam(Base):
    __tablename__ = "entrance_exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    duration_minutes = Column(Integer, default=60)
    passing_score = Column(Float, default=60.0)  # percentage
    max_attempts = Column(Integer, default=0)  # 0 = unlimited
    fee = Column(Float, default=0.0)
    cooldown_days = Column(Integer, default=0)
    questions_per_attempt = Column(Integer, nullable=True)  # null = all questions; otherwise random N from pool
    is_active = Column(Boolean, default=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EntranceExam {self.title}>"


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="mcq")  # mcq, true_false
    marks = Column(Float, default=1.0)
    order = Column(Integer, default=0)
    category = Column(String(100), nullable=True)
    negative_marks = Column(Float, default=0.0)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    exam = relationship("EntranceExam", back_populates="questions")
    options = relationship("ExamOption", back_populates="question", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExamQuestion {self.id}>"


class ExamOption(Base):
    __tablename__ = "exam_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("exam_questions.id", ondelete="CASCADE"), nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)

    # relationships
    question = relationship("ExamQuestion", back_populates="options")

    def __repr__(self):
        return f"<ExamOption {self.id}>"


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    is_submitted = Column(Boolean, default=False)
    time_spent_seconds = Column(Integer, nullable=True)
    needs_manual_evaluation = Column(Boolean, default=False)

    # relationships
    exam = relationship("EntranceExam", back_populates="attempts")
    answers = relationship("ExamAnswer", back_populates="attempt", cascade="all, delete-orphan")
    result = relationship("ExamResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExamAttempt user={self.user_id} exam={self.exam_id}>"


class ExamAnswer(Base):
    __tablename__ = "exam_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("exam_questions.id", ondelete="CASCADE"), nullable=False)
    selected_option_id = Column(Integer, ForeignKey("exam_options.id"), nullable=True)
    descriptive_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    answered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    attempt = relationship("ExamAttempt", back_populates="answers")

    def __repr__(self):
        return f"<ExamAnswer attempt={self.attempt_id} question={self.question_id}>"


class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False)
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    total_marks = Column(Float, default=0.0)
    obtained_marks = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # relationships
    attempt = relationship("ExamAttempt", back_populates="result")

    def __repr__(self):
        return f"<ExamResult attempt={self.attempt_id} passed={self.passed}>"


# --- COURSE & MONTHLY EXAMS ---

class CourseExam(Base):
    __tablename__ = "course_exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    module_id = Column(Integer, ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=True)
    exam_type = Column(String(50), default="course_final") # course_final, module_final, monthly
    duration_minutes = Column(Integer, default=60)
    passing_score = Column(Float, default=60.0)  # percentage
    max_attempts = Column(Integer, default=3)
    questions_per_attempt = Column(Integer, nullable=True)  # null = all questions; otherwise random N from pool
    is_active = Column(Boolean, default=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    questions = relationship("CourseExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("CourseExamAttempt", back_populates="exam", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CourseExam {self.title}>"

class CourseExamQuestion(Base):
    __tablename__ = "course_exam_questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="mcq")  # mcq, true_false
    marks = Column(Float, default=1.0)
    order = Column(Integer, default=0)
    category = Column(String(100), nullable=True)
    negative_marks = Column(Float, default=0.0)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    exam = relationship("CourseExam", back_populates="questions")
    options = relationship("CourseExamOption", back_populates="question", cascade="all, delete-orphan")

class CourseExamOption(Base):
    __tablename__ = "course_exam_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("course_exam_questions.id", ondelete="CASCADE"), nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)

    question = relationship("CourseExamQuestion", back_populates="options")

class CourseExamAttempt(Base):
    __tablename__ = "course_exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    is_submitted = Column(Boolean, default=False)
    time_spent_seconds = Column(Integer, nullable=True)
    device_id = Column(String(255), nullable=True) # For single device restriction
    needs_manual_evaluation = Column(Boolean, default=False)

    # relationships
    exam = relationship("CourseExam", back_populates="attempts")
    answers = relationship("CourseExamAnswer", back_populates="attempt", cascade="all, delete-orphan")
    result = relationship("CourseExamResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")
    violations = relationship("ExamViolation", back_populates="attempt", cascade="all, delete-orphan")

class CourseExamAnswer(Base):
    __tablename__ = "course_exam_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("course_exam_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("course_exam_questions.id", ondelete="CASCADE"), nullable=False)
    selected_option_id = Column(Integer, ForeignKey("course_exam_options.id"), nullable=True)
    descriptive_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    answered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    attempt = relationship("CourseExamAttempt", back_populates="answers")

class CourseExamResult(Base):
    __tablename__ = "course_exam_results"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("course_exam_attempts.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=False)
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    total_marks = Column(Float, default=0.0)
    obtained_marks = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    attempt = relationship("CourseExamAttempt", back_populates="result")

class MonthlyExam(Base):
    __tablename__ = "monthly_exams"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    month_number = Column(Integer, nullable=False) # 1, 2, 3
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    exam = relationship("CourseExam")

class ExamPayment(Base):
    __tablename__ = "exam_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="pending") # pending, paid
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EntranceExamPayment(Base):
    __tablename__ = "entrance_exam_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entrance_exam_id = Column(Integer, ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="pending") # pending, paid
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ExamViolation(Base):
    __tablename__ = "exam_violations"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("course_exam_attempts.id", ondelete="CASCADE"), nullable=False)
    violation_type = Column(String(100), nullable=False) # tab_switch, camera_off
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # relationships
    attempt = relationship("CourseExamAttempt", back_populates="violations")


# --- SKILL-BASED RESULT ANALYSIS ---

class CategoryScore(Base):
    """Per-category score breakdown for skill analysis."""
    __tablename__ = "category_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, ForeignKey("course_exams.id", ondelete="CASCADE"), nullable=True)
    category = Column(String(100), nullable=False)  # e.g. "Technical Analysis", "Risk Management"
    score = Column(Float, default=0.0)
    max_score = Column(Float, default=100.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CategoryScore user={self.user_id} category={self.category} score={self.score}>"

