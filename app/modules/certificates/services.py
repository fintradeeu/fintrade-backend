"""Certificates module — service layer with PDF generation via reportlab."""

import os
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.certificates.models import Certificate
from app.modules.courses.models import CourseEnrollment, Course
from app.modules.auth.models import User


async def generate_certificate(db: AsyncSession, user_id: int, course_id: int) -> Certificate:
    """Generate a certificate after course completion."""

    # 1. Check enrollment exists and is completed
    enroll_result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.is_active == True,
        )
    )
    enrollment = enroll_result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=404, detail="No active enrollment found for this course")

    if enrollment.progress_percent < 100.0:
        raise HTTPException(
            status_code=400,
            detail=f"Course not completed. Progress: {enrollment.progress_percent}%",
        )

    # 1.5 Check if course has a final exam, and if so, check if passed
    from app.modules.exams.models import CourseExam, CourseExamResult
    final_exam_res = await db.execute(
        select(CourseExam).where(
            CourseExam.course_id == course_id,
            CourseExam.exam_type == "course_final",
            CourseExam.is_active == True
        )
    )
    final_exam = final_exam_res.scalar_one_or_none()
    if final_exam:
        passed_res = await db.execute(
            select(CourseExamResult).where(
                CourseExamResult.user_id == user_id,
                CourseExamResult.exam_id == final_exam.id,
                CourseExamResult.passed == True
            )
        )
        if not passed_res.scalars().first():
            raise HTTPException(
                status_code=403,
                detail="You must pass the course's final exam to generate the certificate."
            )

    # 2. Check duplicate
    existing = await db.execute(
        select(Certificate).where(
            Certificate.user_id == user_id,
            Certificate.course_id == course_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Certificate already issued for this course")

    # 3. Fetch user and course names for PDF
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalar_one()

    # 4. Generate unique code and PDF
    unique_code = uuid.uuid4().hex[:12].upper()
    pdf_filename = f"cert_{unique_code}.pdf"
    pdf_dir = os.path.join("uploads", "certificates")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    _generate_pdf(pdf_path, user.full_name, course.title, unique_code)

    certificate_url = f"/uploads/certificates/{pdf_filename}"

    # 5. Save to DB
    cert = Certificate(
        user_id=user_id,
        course_id=course_id,
        unique_code=unique_code,
        certificate_url=certificate_url,
    )
    db.add(cert)
    await db.flush()
    await db.refresh(cert)
    return cert


async def get_certificate(db: AsyncSession, cert_id: int, user_id: int) -> Certificate:
    """Get a certificate by ID (user can only view their own)."""
    result = await db.execute(
        select(Certificate).where(Certificate.id == cert_id, Certificate.user_id == user_id)
    )
    cert = result.scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


async def get_certificate_for_download(db: AsyncSession, cert_id: int, user_id: int) -> str:
    """Return the file path for download."""
    cert = await get_certificate(db, cert_id, user_id)
    if not cert.certificate_url:
        raise HTTPException(status_code=404, detail="Certificate PDF not available")
    # certificate_url is like /uploads/certificates/cert_XYZ.pdf
    file_path = cert.certificate_url.lstrip("/")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Certificate file not found on disk")
    return file_path


def _generate_pdf(filepath: str, student_name: str, course_title: str, unique_code: str):
    """Generate a certificate PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import HexColor
    except ImportError:
        # Fallback: write a simple text file if reportlab is not installed
        with open(filepath, "w") as f:
            f.write(f"CERTIFICATE OF COMPLETION\n\n")
            f.write(f"This certifies that {student_name}\n")
            f.write(f"has successfully completed the course: {course_title}\n")
            f.write(f"Certificate Code: {unique_code}\n")
            f.write(f"Issued: {datetime.now(timezone.utc).strftime('%B %d, %Y')}\n")
        return

    c = canvas.Canvas(filepath, pagesize=landscape(A4))
    width, height = landscape(A4)

    # Background
    c.setFillColor(HexColor("#1a1a2e"))
    c.rect(0, 0, width, height, fill=1)

    # Border
    c.setStrokeColor(HexColor("#e94560"))
    c.setLineWidth(3)
    c.rect(30, 30, width - 60, height - 60, fill=0)

    # Inner border
    c.setStrokeColor(HexColor("#0f3460"))
    c.setLineWidth(1)
    c.rect(45, 45, width - 90, height - 90, fill=0)

    # Title
    c.setFillColor(HexColor("#e94560"))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width / 2, height - 120, "CERTIFICATE OF COMPLETION")

    # Subtitle
    c.setFillColor(HexColor("#16213e"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 155, "FItTrade Learning Management System")

    # Divider
    c.setStrokeColor(HexColor("#e94560"))
    c.setLineWidth(2)
    c.line(width / 2 - 150, height - 170, width / 2 + 150, height - 170)

    # Body text
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 210, "This is to certify that")

    # Student Name
    c.setFillColor(HexColor("#e94560"))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 250, student_name)

    # Course completion text
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 290, "has successfully completed the course")

    # Course Title
    c.setFillColor(HexColor("#0f3460"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 325, course_title)

    # Date
    c.setFillColor(HexColor("#cccccc"))
    c.setFont("Helvetica", 12)
    issued_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    c.drawCentredString(width / 2, height - 380, f"Issued on: {issued_date}")

    # Unique code
    c.setFillColor(HexColor("#888888"))
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, 70, f"Certificate Code: {unique_code}")

    c.save()
