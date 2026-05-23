"""Payments module — services."""

import hashlib
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.logger import get_logger
from app.modules.payments.models import PaymentTransaction
from app.modules.courses.models import Course
from app.modules.auth.models import User
from app.modules.courses.services import enroll_user
from app.utils.smtp_notifications import send_email

logger = get_logger(__name__)

def generate_hash(data_string: str) -> str:
    """Generate SHA512 hash for Easebuzz."""
    return hashlib.sha512(data_string.encode('utf-8')).hexdigest()

async def initiate_payment(db: AsyncSession, user: User, course_id: int, base_url: str) -> dict:
    """Initiate an Easebuzz payment for a course."""
    if not settings.EASEBUZZ_KEY or not settings.EASEBUZZ_SALT:
        raise HTTPException(status_code=500, detail="Payment gateway is not configured")

    # Verify course
    course = await db.get(Course, course_id)
    if not course or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found or not published")
    
    if not course.price or course.price <= 0:
        raise HTTPException(status_code=400, detail="Free courses do not require payment")

    # Entrance Exam Prerequisite Check
    from app.modules.exams.models import EntranceExam, ExamResult
    entrance_res = await db.execute(
        select(EntranceExam).where(
            EntranceExam.course_id == course_id,
            EntranceExam.is_active == True
        )
    )
    entrance_exam = entrance_res.scalar_one_or_none()
    if entrance_exam:
        passed_res = await db.execute(
            select(ExamResult).where(
                ExamResult.user_id == user.id,
                ExamResult.exam_id == entrance_exam.id,
                ExamResult.passed == True
            )
        )
        if not passed_res.scalars().first():
            raise HTTPException(
                status_code=403,
                detail="You must pass the entrance exam before you can purchase this course."
            )

    # Generate unique txnid
    txnid = f"TXN{uuid.uuid4().hex[:12].upper()}"
    amount_str = f"{course.price:.2f}"
    productinfo = "Course"
    firstname = (user.full_name or "Student").strip()
    email = user.email.strip()
    phone = user.phone or "9999999999"
    
    # Create pending transaction
    transaction = PaymentTransaction(
        user_id=user.id,
        course_id=course_id,
        txnid=txnid,
        amount=course.price,
        status="pending"
    )
    db.add(transaction)
    await db.flush()

    # Generate Hash
    # Format: key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|udf6|udf7|udf8|udf9|udf10|salt
    hash_string = f"{settings.EASEBUZZ_KEY}|{txnid}|{amount_str}|{productinfo}|{firstname}|{email}|||||||||||{settings.EASEBUZZ_SALT}"
    hashed = generate_hash(hash_string)

    base_url = base_url.rstrip('/')
    # Force https in production to prevent 301 redirects that drop POST data
    if "api.thefintrade.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
        
    payload = {
        "key": settings.EASEBUZZ_KEY,
        "txnid": txnid,
        "amount": amount_str,
        "productinfo": productinfo,
        "firstname": firstname,
        "phone": phone,
        "email": email,
        "surl": f"{base_url}/payments/success",  # Backend POST redirect
        "furl": f"{base_url}/payments/failure",  # Backend POST redirect
        "hash": hashed
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    url = f"{settings.easebuzz_base_url}/payment/initiateLink"
    logger.info("easebuzz_initiate_req", txnid=txnid, amount=amount_str)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("easebuzz_initiate_error", error=str(e))
            raise HTTPException(status_code=502, detail="Failed to initiate payment with gateway")

    if data.get("status") != 1:
        logger.error("easebuzz_initiate_failed", data=data)
        raise HTTPException(status_code=400, detail="Gateway rejected payment initiation")

    access_key = data["data"]
    redirect_url = f"{settings.easebuzz_base_url}/pay/{access_key}"

    await db.commit()
    return {
        "txnid": txnid,
        "access_key": access_key,
        "redirect_url": redirect_url
    }

async def process_webhook(db: AsyncSession, form_data: dict) -> dict:
    """Process incoming webhook from Easebuzz."""
    logger.info("easebuzz_webhook_received", form_data=form_data)

    txnid = form_data.get("txnid")
    status = form_data.get("status")
    amount = form_data.get("amount")
    productinfo = form_data.get("productinfo")
    firstname = form_data.get("firstname")
    email = form_data.get("email")
    received_hash = form_data.get("hash")
    easepayid = form_data.get("easepayid")
    payment_mode = form_data.get("mode")

    if not all([txnid, status, amount, productinfo, firstname, email, received_hash]):
        logger.warning("easebuzz_webhook_missing_fields")
        return {"status": "error", "message": "Missing fields"}

    # Reverse hash for verification
    # Format: salt|status|udf10|udf9|udf8|udf7|udf6|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    hash_string = f"{settings.EASEBUZZ_SALT}|{status}|||||||||||{email}|{firstname}|{productinfo}|{amount}|{txnid}|{settings.EASEBUZZ_KEY}"
    calculated_hash = generate_hash(hash_string)

    if calculated_hash != received_hash:
        logger.error("easebuzz_webhook_invalid_hash", txnid=txnid)
        return {"status": "error", "message": "Invalid hash"}

    # Fetch transaction
    res = await db.execute(select(PaymentTransaction).where(PaymentTransaction.txnid == txnid))
    transaction = res.scalar_one_or_none()
    if not transaction:
        logger.error("easebuzz_webhook_txnid_not_found", txnid=txnid)
        return {"status": "error", "message": "Transaction not found"}

    # Idempotency check
    if transaction.status == "success":
        logger.info("easebuzz_webhook_already_processed", txnid=txnid)
        return {"status": "ok", "message": "Already processed"}

    # Update transaction
    transaction.easepayid = easepayid
    transaction.status = status.lower()
    transaction.payment_mode = payment_mode
    transaction.gateway_response = form_data
    transaction.updated_at = datetime.now(timezone.utc)

    if status.lower() == "success":
        try:
            # Grant course access
            await enroll_user(db, user_id=transaction.user_id, course_id=transaction.course_id)
            logger.info("easebuzz_course_unlocked", txnid=txnid, user_id=transaction.user_id, course_id=transaction.course_id)
            
            # Send Email Invoice asynchronously
            user = await db.get(User, transaction.user_id)
            course = await db.get(Course, transaction.course_id)
            if user and course:
                await send_invoice_email(user, course, transaction)

        except Exception as e:
            logger.error("easebuzz_course_unlock_failed", txnid=txnid, error=str(e))
            # Even if enroll fails, we should commit the success status and investigate manually
            # But normally enroll_user works unless already enrolled

    await db.commit()
    return {"status": "ok"}


async def send_invoice_email(user: User, course: Course, transaction: PaymentTransaction):
    """Send an invoice email for the successful purchase."""
    subject = f"Invoice for {course.title} - FinTrade LMS"
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Payment Successful!</h2>
        <p>Hi {user.full_name},</p>
        <p>Thank you for purchasing <strong>{course.title}</strong>.</p>
        <table style="width: 100%; max-width: 500px; border-collapse: collapse; margin-top: 20px;">
            <tr style="background: #f8f8f8;">
                <td style="padding: 10px; border: 1px solid #ddd;"><strong>Transaction ID</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{transaction.txnid}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;"><strong>Amount Paid</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">₹{transaction.amount}</td>
            </tr>
            <tr style="background: #f8f8f8;">
                <td style="padding: 10px; border: 1px solid #ddd;"><strong>Date</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{transaction.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</td>
            </tr>
        </table>
        <p style="margin-top: 20px;">You can now log in to your dashboard to access the course.</p>
        <p>Happy Learning!<br>FinTrade Team</p>
    </body>
    </html>
    """
    await send_email(to_email=user.email, subject=subject, body_html=body_html)
