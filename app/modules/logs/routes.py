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
    await db.flush() # get log_entry.id
    
    # Process extended metadata if provided in metadata_json
    if body.metadata_json:
        metadata_model = models.ActivityLogMetadata(
            activity_log_id=log_entry.id,
            referrer=body.metadata_json.get("referrer"),
            user_agent=body.metadata_json.get("userAgent"),
            browser=body.metadata_json.get("browser"),
            browser_version=body.metadata_json.get("browserVersion"),
            os=body.metadata_json.get("os"),
            os_version=body.metadata_json.get("osVersion"),
            device_type=body.metadata_json.get("deviceType"),
            screen_width=body.metadata_json.get("screenWidth"),
            screen_height=body.metadata_json.get("screenHeight"),
            language=body.metadata_json.get("language"),
            timezone=body.metadata_json.get("timezone"),
            ip_address=body.metadata_json.get("ipAddress"),
            latitude=body.metadata_json.get("latitude"),
            longitude=body.metadata_json.get("longitude"),
            country=body.metadata_json.get("country"),
            state=body.metadata_json.get("state"),
            city=body.metadata_json.get("city"),
            postal_code=body.metadata_json.get("postalCode"),
            permission_status=body.metadata_json.get("permissionStatus"),
            app_version=body.metadata_json.get("appVersion"),
            build_number=body.metadata_json.get("buildNumber")
        )
        db.add(metadata_model)
        
    await db.commit()
    await db.refresh(log_entry)
    
    # Eager load user and log_metadata if exists
    result = await db.execute(
        select(models.ActivityLog)
        .options(selectinload(models.ActivityLog.user))
        .options(selectinload(models.ActivityLog.log_metadata))
        .where(models.ActivityLog.id == log_entry.id)
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
        .options(selectinload(models.ActivityLog.log_metadata))
        .order_by(models.ActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()
