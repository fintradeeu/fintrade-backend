import asyncio
import datetime
import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.modules.payments.models import StudentInstallment
from app.modules.auth.models import User
from app.modules.courses.models import Course
from app.utils.smtp_notifications import send_email
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def send_reminders():
    logger.info("Starting installment reminders job...")
    now = datetime.datetime.now(datetime.timezone.utc)
    # Find installments due tomorrow
    tomorrow_start = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + datetime.timedelta(days=1)
    
    async with SessionLocal() as db:
        stmt = (
            select(StudentInstallment, User, Course)
            .join(User, StudentInstallment.user_id == User.id)
            .join(Course, StudentInstallment.course_id == Course.id)
            .where(StudentInstallment.status == "pending")
            .where(StudentInstallment.due_date >= tomorrow_start)
            .where(StudentInstallment.due_date < tomorrow_end)
        )
        result = await db.execute(stmt)
        records = result.all()
        
        logger.info(f"Found {len(records)} installments due tomorrow.")
        
        for installment, user, course in records:
            subject = f"Reminder: Upcoming EMI Payment for {course.title}"
            body_html = f"""
            <html>
                <body>
                    <h2>Payment Reminder</h2>
                    <p>Dear {user.full_name},</p>
                    <p>This is a gentle reminder that your installment payment for the course <strong>{course.title}</strong> is due tomorrow ({installment.due_date.strftime('%B %d, %Y')}).</p>
                    <p><strong>Installment No:</strong> {installment.installment_no}</p>
                    <p><strong>Amount Due:</strong> ₹{installment.amount:,.2f}</p>
                    <br>
                    <p>Please ensure the payment is made on time to avoid any interruption to your course access.</p>
                    <p>Thank you,<br>FinTrade Edutech Team</p>
                </body>
            </html>
            """
            try:
                await send_email(user.email, subject, body_html)
                logger.info(f"Sent reminder to {user.email} for installment ID {installment.id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user.email}: {str(e)}")
                
    logger.info("Finished installment reminders job.")

if __name__ == "__main__":
    asyncio.run(send_reminders())
