from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.db.database import get_db
from app.modules.logs import schemas, models
from app.modules.auth.models import User
from app.core.security import require_roles, decode_token

router = APIRouter(prefix="/logs", tags=["Activity Logs"])

def get_user_from_request(request: Request, db: AsyncSession):
    # This is a synchronous extraction for ease, wait it needs async db access.
    # We will do it in the route.
    pass

@router.post("/activity", response_model=schemas.ActivityLogResponse, status_code=201)
async def create_activity_log(
    body: schemas.ActivityLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            user_id = int(payload.get("sub"))
        except Exception:
            pass

    log_entry = models.ActivityLog(
        user_id=user_id,
        module=body.module,
        action=body.action,
        description=body.description,
        status_code=body.status_code or 200,
        status_text=body.status_text or "SUCCESS",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        location_data=body.location_data,
        device_data=body.device_data,
        metadata_json=body.metadata_json,
        tenant_id=body.tenant_id,
        suspicious=body.suspicious,
    )
    
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    
    # Eager load user if exists
    if log_entry.user_id:
        # reload with user
        result = await db.execute(
            select(models.ActivityLog).options(selectinload(models.ActivityLog.user)).where(models.ActivityLog.id == log_entry.id)
        )
        log_entry = result.scalar_one()

    return log_entry

@router.get("/activity", response_model=List[schemas.ActivityLogResponse])
async def list_activity_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_roles(["super_admin", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.ActivityLog)
        .options(selectinload(models.ActivityLog.user))
        .order_by(models.ActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()
