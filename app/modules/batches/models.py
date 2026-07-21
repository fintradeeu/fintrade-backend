"""Batches module — database models."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    batch_code = Column(String(100), unique=True, nullable=False, index=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    registration_start_date = Column(DateTime(timezone=True), nullable=False)
    registration_end_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        SAEnum("Upcoming", "Registration Open", "Registration Closed", "Running", "Completed", "Archived", name="batch_status"),
        default="Upcoming",
        nullable=False,
    )
    thumbnail_url = Column(Text, nullable=True)
    banner_url = Column(Text, nullable=True)
    max_students = Column(Integer, default=100, nullable=False)
    current_students = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    courses = relationship("BatchCourse", back_populates="batch", cascade="all, delete-orphan")
    modules = relationship("BatchModule", back_populates="batch", cascade="all, delete-orphan", order_by="BatchModule.order")
    lectures = relationship("BatchLecture", back_populates="batch", cascade="all, delete-orphan", order_by="BatchLecture.scheduled_at")
    enrollments = relationship("StudentBatchEnrollment", back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Batch {self.name} ({self.batch_code})>"


class BatchCourse(Base):
    __tablename__ = "batch_courses"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("Batch", back_populates="courses")
    course = relationship("Course")


class BatchModule(Base):
    __tablename__ = "batch_modules"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    template_module_id = Column(Integer, ForeignKey("course_modules.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("Batch", back_populates="modules")
    course = relationship("Course")
    lessons = relationship("BatchLesson", back_populates="module", cascade="all, delete-orphan", order_by="BatchLesson.order")


class BatchLesson(Base):
    __tablename__ = "batch_lessons"

    id = Column(Integer, primary_key=True, index=True)
    batch_module_id = Column(Integer, ForeignKey("batch_modules.id", ondelete="CASCADE"), nullable=False)
    template_lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(50), default="text")  # text, video, pdf, quiz
    video_url = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    order = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    module = relationship("BatchModule", back_populates="lessons")


class BatchLecture(Base):
    __tablename__ = "batch_lectures"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    meeting_link = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=60, nullable=False)
    is_live = Column(Boolean, default=False, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    instructor_name = Column(String(255), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("Batch", back_populates="lectures")
    course = relationship("Course")


class StudentBatchEnrollment(Base):
    __tablename__ = "student_batch_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    price_paid = Column(Float, default=0.0, nullable=False)
    discount_applied = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    payment_status = Column(String(50), default="full", nullable=False)
    allowed_modules = Column(JSON, nullable=True)
    payment_due_date = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    batch = relationship("Batch", back_populates="enrollments")
    user = relationship("User")


class BatchAssignment(Base):
    __tablename__ = "batch_assignments"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    batch_module_id = Column(Integer, ForeignKey("batch_modules.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    max_score = Column(Float, default=100.0, nullable=False)
    resources = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("Batch")
    course = relationship("Course")
    module = relationship("BatchModule")
    submissions = relationship("BatchAssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


class BatchAssignmentSubmission(Base):
    __tablename__ = "batch_assignment_submissions"

    id = Column(Integer, primary_key=True, index=True)
    batch_assignment_id = Column(Integer, ForeignKey("batch_assignments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default="submitted", nullable=False)  # submitted, graded
    score = Column(Float, nullable=True)
    teacher_feedback = Column(Text, nullable=True)

    # Relationships
    assignment = relationship("BatchAssignment", back_populates="submissions")
    user = relationship("User")


class BatchLessonCompletion(Base):
    __tablename__ = "batch_lesson_completions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    batch_lesson_id = Column(Integer, ForeignKey("batch_lessons.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch_lesson = relationship("BatchLesson")
    user = relationship("User")


class BatchDayTask(Base):
    __tablename__ = "batch_day_tasks"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    day_number = Column(Integer, nullable=False)  # e.g. -5, -4, 1, 2
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), default="text")  # text, video, pdf, quiz
    content = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    # Live Lecture Fields
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    instructor_name = Column(String(255), nullable=True)
    
    # Exam Fields
    exam_title = Column(String(255), nullable=True)
    exam_passing_score = Column(Float, nullable=True)
    
    # Linked Entities
    linked_assignment_id = Column(Integer, ForeignKey("batch_assignments.id", ondelete="SET NULL"), nullable=True)

    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("Batch")
    course = relationship("Course")
    linked_assignment = relationship("BatchAssignment")
