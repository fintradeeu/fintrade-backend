"""Payments module — services."""

import hashlib
import hmac
import uuid
import httpx
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
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

def _active_gateway() -> str:
    return (settings.ACTIVE_PAYMENT_GATEWAY or "").strip().lower()

def _razorpay_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)

async def _create_razorpay_order(txnid: str, amount: float, course_id: int, user_id: int) -> dict:
    if not _razorpay_configured():
        raise HTTPException(
            status_code=500,
            detail="Razorpay is selected but RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET is missing.",
        )

    amount_paise = int(round(amount * 100))
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": txnid,
        "notes": {
            "course_id": str(course_id),
            "user_id": str(user_id),
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.razorpay.com/v1/orders",
                json=payload,
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("razorpay_order_rejected", status=e.response.status_code, response=e.response.text)
            raise HTTPException(status_code=502, detail="Razorpay rejected payment initiation")
        except Exception as e:
            logger.error("razorpay_order_error", error=str(e))
            raise HTTPException(status_code=502, detail="Failed to initiate payment with Razorpay")

    return {
        "gateway": "razorpay",
        "txnid": txnid,
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": data["id"],
        "amount": amount_paise,
        "currency": data.get("currency", "INR"),
    }

async def initiate_payment(
    db: AsyncSession,
    user: User,
    course_id: int,
    base_url: str,
    coupon_code: str | None = None,
    discounted_price: float | None = None,
) -> dict:
    """Initiate a configured gateway payment for a course."""

    # Verify course
    course = await db.get(Course, course_id)
    if not course or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found or not published")
    
    if not course.price or course.price <= 0:
        raise HTTPException(status_code=400, detail="Free courses do not require payment")

    # --- Discount / Coupon ---
    # The coupon was already validated server-side at POST /offers/apply.
    # At payment time we simply use the pre-validated discounted_price sent by the frontend.
    # We still sanity-check: it must be positive and less than the full course price.
    if discounted_price is not None and 0 < discounted_price < course.price:
        charge_amount = discounted_price
    else:
        charge_amount = course.price

    logger.info("payment_charge_amount", course_id=course_id, course_price=course.price,
                coupon_code=coupon_code, discounted_price=discounted_price, charge_amount=charge_amount)

    # Entrance Exam Prerequisite Check
    from app.modules.exams.models import EntranceExam, ExamResult
    entrance_res = await db.execute(
        select(EntranceExam).where(
            EntranceExam.course_id == course_id,
            EntranceExam.is_active == True
        )
    )
    exams = entrance_res.scalars().all()
    if exams:
        exam_ids = [e.id for e in exams]
        passed_res = await db.execute(
            select(ExamResult).where(
                ExamResult.user_id == user.id,
                ExamResult.exam_id.in_(exam_ids),
                ExamResult.passed == True
            )
        )
        if not passed_res.scalars().first():
            raise HTTPException(
                status_code=403,
                detail="You must pass the entrance exam before you can purchase this course."
            )

    if _active_gateway() == "razorpay":
        txnid = f"TXN{uuid.uuid4().hex[:12].upper()}"
        transaction = PaymentTransaction(
            user_id=user.id,
            course_id=course_id,
            txnid=txnid,
            amount=charge_amount,
            status="pending",
            coupon_code=coupon_code,
            payment_mode="razorpay",
        )
        db.add(transaction)
        await db.flush()

        order = await _create_razorpay_order(
            txnid=txnid,
            amount=charge_amount,
            course_id=course_id,
            user_id=user.id,
        )
        transaction.gateway_response = {"razorpay_order_id": order["order_id"]}
        await db.commit()
        return order

    # If Easebuzz is not configured, fall back to Sandbox mockup flow
    if not settings.EASEBUZZ_KEY or not settings.EASEBUZZ_SALT:
        txnid = f"TXN{uuid.uuid4().hex[:12].upper()}"
        amount_str = f"{charge_amount:.2f}"
        
        # Create pending transaction
        transaction = PaymentTransaction(
            user_id=user.id,
            course_id=course_id,
            txnid=txnid,
            amount=charge_amount,
            status="pending",
            coupon_code=coupon_code
        )
        db.add(transaction)
        await db.commit()
        
        clean_base = base_url.rstrip('/')
        return {
            "txnid": txnid,
            "access_key": "MOCK_KEY",
            "redirect_url": f"{clean_base}/payments/mock-checkout?txnid={txnid}"
        }

    # Generate unique txnid
    txnid = f"TXN{uuid.uuid4().hex[:12].upper()}"
    amount_str = f"{charge_amount:.2f}"
    productinfo = "Course"
    firstname = (user.full_name or "Student").strip()
    email = user.email.strip()
    phone = user.phone or "9999999999"
    
    # Create pending transaction
    transaction = PaymentTransaction(
        user_id=user.id,
        course_id=course_id,
        txnid=txnid,
        amount=charge_amount,
        status="pending",
        coupon_code=coupon_code
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

async def verify_razorpay_payment(
    db: AsyncSession,
    user_id: int,
    txnid: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict:
    """Verify Razorpay checkout signature and unlock the purchased course."""
    if not _razorpay_configured():
        raise HTTPException(status_code=500, detail="Razorpay is not configured on the server")

    res = await db.execute(select(PaymentTransaction).where(PaymentTransaction.txnid == txnid))
    transaction = res.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.user_id != user_id:
        raise HTTPException(status_code=403, detail="Transaction does not belong to this user")

    if transaction.status == "success":
        return {"status": "ok", "message": "Already verified"}

    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, razorpay_signature):
        transaction.status = "failed"
        transaction.gateway_response = {
            **(transaction.gateway_response or {}),
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "verification_error": "invalid_signature",
        }
        transaction.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    stored_order_id = (transaction.gateway_response or {}).get("razorpay_order_id")
    if stored_order_id and stored_order_id != razorpay_order_id:
        raise HTTPException(status_code=400, detail="Razorpay order does not match this transaction")

    transaction.easepayid = razorpay_payment_id
    transaction.status = "success"
    transaction.payment_mode = "razorpay"
    transaction.gateway_response = {
        **(transaction.gateway_response or {}),
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    }
    transaction.updated_at = datetime.now(timezone.utc)

    try:
        await enroll_user(
            db,
            user_id=transaction.user_id,
            course_id=transaction.course_id,
            distributor_code=transaction.coupon_code,
        )
        logger.info("razorpay_course_unlocked", txnid=txnid, user_id=transaction.user_id, course_id=transaction.course_id)
    except HTTPException as e:
        if e.status_code != 409:
            raise
        logger.info("razorpay_course_already_unlocked", txnid=txnid, user_id=transaction.user_id, course_id=transaction.course_id)
    except Exception as e:
        logger.error("razorpay_course_unlock_failed", txnid=txnid, error=str(e))
        raise HTTPException(status_code=500, detail="Payment verified, but course unlock failed")

    user = await db.get(User, transaction.user_id)
    course = await db.get(Course, transaction.course_id)
    if user and course:
        try:
            await send_invoice_email(user, course, transaction)
        except Exception as e:
            logger.error("razorpay_invoice_email_failed", txnid=txnid, error=str(e))

    await db.commit()
    return {"status": "ok"}

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
    if settings.EASEBUZZ_KEY and settings.EASEBUZZ_SALT and received_hash != "MOCK_HASH":
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
            await enroll_user(
                db,
                user_id=transaction.user_id,
                course_id=transaction.course_id,
                distributor_code=transaction.coupon_code
            )
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
