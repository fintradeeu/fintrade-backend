"""Payments module — API routes."""

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

from app.db.database import get_db
from app.core.security import get_current_user
from app.modules.auth.models import User
from app.modules.payments import schemas, services

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/create", response_model=schemas.PaymentInitiateResponse)
async def create_payment(
    body: schemas.PaymentInitiateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a course payment via Easebuzz."""
    return await services.initiate_payment(
        db,
        user=current_user,
        course_id=body.course_id,
        base_url=str(request.base_url),
        coupon_code=body.coupon_code,
        discounted_price=body.discounted_price,
    )

@router.post("/success")
async def payment_success_redirect(request: Request, db: AsyncSession = Depends(get_db)):
    """Easebuzz redirects here on success via POST."""
    form_data = await request.form()
    form_dict = dict(form_data)
    
    # Process it just like a webhook (idempotent, safe fallback for localhost)
    await services.process_webhook(db, form_data=form_dict)
    
    txnid = form_data.get("txnid", "")
    frontend_url = settings.CORS_ORIGINS.split(',')[0]
    return RedirectResponse(url=f"{frontend_url}/payment/success?txnid={txnid}", status_code=303)

@router.post("/failure")
async def payment_failure_redirect(request: Request, db: AsyncSession = Depends(get_db)):
    """Easebuzz redirects here on failure/cancel via POST."""
    form_data = await request.form()
    form_dict = dict(form_data)
    
    # Process it just like a webhook (idempotent, safe fallback for localhost)
    await services.process_webhook(db, form_data=form_dict)

    txnid = form_data.get("txnid", "")
    frontend_url = settings.CORS_ORIGINS.split(',')[0]
    return RedirectResponse(url=f"{frontend_url}/payment/failure?txnid={txnid}", status_code=303)

@router.post("/webhook")
async def easebuzz_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Receive and process Easebuzz payment webhook."""
    # Webhooks come as form-urlencoded data
    form_data = await request.form()
    # Convert immutable FormData to dict
    form_dict = dict(form_data)
    
    return await services.process_webhook(db, form_data=form_dict)


@router.get("/mock-checkout")
async def mock_checkout(txnid: str, db: AsyncSession = Depends(get_db)):
    """Render a beautiful mock payment gateway page for testing."""
    from sqlalchemy import select
    from app.modules.payments.models import PaymentTransaction
    from app.modules.courses.models import Course
    from app.modules.auth.models import User
    from fastapi.responses import HTMLResponse

    res = await db.execute(select(PaymentTransaction).where(PaymentTransaction.txnid == txnid))
    transaction = res.scalar_one_or_none()
    if not transaction:
        return HTMLResponse(content="<h3>Transaction not found</h3>", status_code=404)

    course = await db.get(Course, transaction.course_id)
    user = await db.get(User, transaction.user_id)
    course_title = course.title if course else "Course"
    course_price = transaction.amount
    user_name = user.full_name if user else "Student"
    user_email = user.email if user else ""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FinTrade Sandbox Payment Gateway</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f3f4f6;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                color: #1f2937;
            }}
            .card {{
                background: white;
                padding: 30px;
                border-radius: 16px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
                width: 100%;
                max-width: 420px;
                box-sizing: border-box;
                border: 1px solid #e5e7eb;
            }}
            .header {{
                text-align: center;
                margin-bottom: 24px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: 800;
                color: #D50032;
                letter-spacing: -0.5px;
            }}
            .tag {{
                font-size: 10px;
                background: #fef2f2;
                color: #ef4444;
                padding: 2px 8px;
                border-radius: 9999px;
                font-weight: 600;
                display: inline-block;
                margin-top: 4px;
                text-transform: uppercase;
            }}
            .item-detail {{
                background: #f9fafb;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 24px;
                border: 1px solid #f3f4f6;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                font-size: 14px;
            }}
            .detail-row:last-child {{
                margin-bottom: 0;
                border-top: 1px dashed #e5e7eb;
                padding-top: 8px;
                margin-top: 8px;
                font-weight: bold;
                font-size: 16px;
            }}
            .label {{ color: #6b7280; }}
            .value {{ color: #111827; }}
            .btn {{
                display: block;
                width: 100%;
                padding: 12px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
                text-align: center;
                cursor: pointer;
                border: none;
                margin-bottom: 12px;
                transition: all 0.2s;
                text-decoration: none;
            }}
            .btn-success {{
                background: #D50032;
                color: white;
            }}
            .btn-success:hover {{
                background: #b8002a;
            }}
            .btn-failure {{
                background: #f3f4f6;
                color: #4b5563;
                border: 1px solid #e5e7eb;
            }}
            .btn-failure:hover {{
                background: #e5e7eb;
            }}
            .footer {{
                text-align: center;
                font-size: 11px;
                color: #9ca3af;
                margin-top: 20px;
            }}
            form {{
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div class="logo">FinTrade</div>
                <div class="tag">Sandbox Payment Gateway</div>
            </div>
            
            <div class="item-detail">
                <div class="detail-row">
                    <span class="label">Course</span>
                    <span class="value">{course_title}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Student</span>
                    <span class="value">{user_name}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Transaction ID</span>
                    <span class="value" style="font-family: monospace; font-size:12px;">{txnid}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Amount</span>
                    <span class="value">₹{course_price:.2f}</span>
                </div>
            </div>

            <form action="/payments/success" method="post">
                <input type="hidden" name="txnid" value="{txnid}" />
                <input type="hidden" name="status" value="success" />
                <input type="hidden" name="amount" value="{course_price:.2f}" />
                <input type="hidden" name="productinfo" value="Course" />
                <input type="hidden" name="firstname" value="{user_name}" />
                <input type="hidden" name="email" value="{user_email}" />
                <input type="hidden" name="hash" value="MOCK_HASH" />
                <button type="submit" class="btn btn-success">Pay Successfully</button>
            </form>

            <form action="/payments/failure" method="post">
                <input type="hidden" name="txnid" value="{txnid}" />
                <input type="hidden" name="status" value="failure" />
                <input type="hidden" name="amount" value="{course_price:.2f}" />
                <input type="hidden" name="productinfo" value="Course" />
                <input type="hidden" name="firstname" value="{user_name}" />
                <input type="hidden" name="email" value="{user_email}" />
                <input type="hidden" name="hash" value="MOCK_HASH" />
                <button type="submit" class="btn btn-failure">Cancel Payment</button>
            </form>

            <div class="footer">
                Secured Sandbox Mode &bull; No real money will be charged
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

