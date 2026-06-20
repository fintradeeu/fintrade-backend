"""Certificates module — service layer with PDF generation via reportlab."""

import os
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    result = await db.execute(
        select(Certificate)
        .options(selectinload(Certificate.course))
        .where(Certificate.id == cert.id)
    )
    cert = result.scalar_one()
    return cert


async def list_certificates_for_user(db: AsyncSession, user_id: int) -> list[Certificate]:
    """List certificates for the current student with course info."""
    result = await db.execute(
        select(Certificate)
        .options(selectinload(Certificate.course))
        .where(Certificate.user_id == user_id)
        .order_by(Certificate.issued_at.desc())
    )
    return list(result.scalars().all())


async def get_certificate(db: AsyncSession, cert_id: int, user_id: int) -> Certificate:
    """Get a certificate by ID (user can only view their own)."""
    result = await db.execute(
        select(Certificate)
        .options(selectinload(Certificate.course))
        .where(Certificate.id == cert_id, Certificate.user_id == user_id)
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
    is_research = "research" in (course_title or "").lower() or "analyst" in (course_title or "").lower()
    issue_date = datetime.now(timezone.utc).strftime("%d %B, %Y").upper()
    cert_no = f"FT-{unique_code}"

    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    red = HexColor("#ef3135")
    dark = HexColor("#111827")
    muted = HexColor("#4b5563")
    gold = HexColor("#d6a32f")

    if is_research:
        c.setFillColor(HexColor("#c8172a"))
        c.rect(0, 0, 165, height, fill=1, stroke=0)
        c.setFillColor(HexColor("#f7c14d"))
        c.rect(165, 0, 7, height, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 22)
        c.drawString(22, height - 42, "The")
        c.setFont("Helvetica-Bold", 30)
        c.drawString(22, height - 72, "FinTrade")
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(58, height - 85, "Learn to Earn")
        content_x = 175
    else:
        c.setFillColor(HexColor("#eeeeee"))
        c.circle(-40, height + 35, 305, fill=1, stroke=0)
        c.setFillColor(red)
        c.circle(-38, height + 35, 275, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.circle(-15, height + 12, 238, fill=1, stroke=0)
        c.setFillColor(HexColor("#eeeeee"))
        c.circle(width + 30, -25, 272, fill=1, stroke=0)
        c.setFillColor(red)
        c.circle(width + 35, -28, 238, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.circle(width + 20, -10, 205, fill=1, stroke=0)
        c.setFillColor(red)
        c.setFont("Helvetica-Bold", 18)
        c.drawRightString(width - 105, height - 36, "The")
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 25)
        c.drawRightString(width - 38, height - 55, "FinTrade")
        c.setFont("Helvetica-Oblique", 8)
        c.drawRightString(width - 38, height - 67, "Learn to Earn")
        content_x = 0

    center_x = content_x + (width - content_x) / 2
    top_y = height - (70 if is_research else 85)
    c.setFillColor(red)
    c.setFont("Times-Bold", 52)
    c.drawCentredString(center_x, top_y, "CERTIFICATE")
    c.setFillColor(dark)
    c.setFont("Times-Bold", 22)
    c.drawCentredString(center_x, top_y - 33, "OF COMPLETION")
    c.setStrokeColor(red)
    c.setLineWidth(0.8)
    c.line(center_x - 70, top_y - 43, center_x + 70, top_y - 43)

    c.setFillColor(dark)
    c.setFont("Helvetica", 24)
    program_name = "Professional Research Analyst Program" if is_research else "Professional Trading Program"
    c.drawCentredString(center_x, top_y - 80, program_name)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(center_x, top_y - 118, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

    c.setFillColor(red)
    c.setFont("Helvetica-Oblique", 38)
    c.drawCentredString(center_x, top_y - 166, student_name)
    c.setStrokeColor(red)
    c.setLineWidth(0.8)
    c.line(center_x - 230, top_y - 178, center_x + 230, top_y - 178)

    c.setFillColor(dark)
    c.setFont("Helvetica", 10)
    c.drawCentredString(center_x, top_y - 203, "For successfully completing the course and gaining practical knowledge in global")
    c.drawCentredString(center_x, top_y - 224, "trade operations, financial instruments, and risk mitigation strategies.")

    signature_y = 138 if is_research else 126
    left_sig_x = center_x - 230
    right_sig_x = center_x + 230
    c.setFillColor(dark)
    c.setFont("Helvetica-Oblique", 27)
    c.drawCentredString(left_sig_x, signature_y + 38, "Hvyas")
    c.drawCentredString(right_sig_x, signature_y + 38, "Chirag")
    c.setStrokeColor(HexColor("#cfa869") if is_research else HexColor("#bdbdbd"))
    c.line(left_sig_x - 80, signature_y + 20, left_sig_x + 80, signature_y + 20)
    c.line(right_sig_x - 80, signature_y + 20, right_sig_x + 80, signature_y + 20)
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(left_sig_x, signature_y, "HET VYAS")
    c.drawCentredString(right_sig_x, signature_y, "CHIRAG PANCHAL")
    c.setFillColor(dark)
    c.setFont("Helvetica", 5)
    c.drawCentredString(left_sig_x, signature_y - 9, "(FOUNDER/COO)")
    c.drawCentredString(right_sig_x, signature_y - 9, "(MD/CEO)")

    if is_research:
        badge_x = center_x
        badge_y = signature_y + 18
        c.setFillColor(gold)
        c.circle(badge_x, badge_y, 38, fill=1, stroke=0)
        c.setFillColor(HexColor("#8b5d00"))
        c.circle(badge_x, badge_y, 31, fill=1, stroke=0)
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(badge_x, badge_y + 2, "CERTIFIED")

    footer_y = 34
    c.setFillColor(red)
    c.circle(center_x - 215, footer_y + 10, 12, fill=1, stroke=0)
    c.circle(center_x + 125, footer_y + 10, 12, fill=1, stroke=0)
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 6)
    c.drawString(center_x - 190, footer_y + 13, "DATE OF COMPLETION")
    c.drawString(center_x + 150, footer_y + 13, "CERTIFICATE NUMBER")
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(center_x - 190, footer_y + 2, issue_date)
    c.drawString(center_x + 150, footer_y + 2, cert_no)

    c.save()
