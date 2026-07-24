from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.database import get_db
from app.modules.devices import schemas, models
from app.modules.auth.models import User
from app.core.security import get_current_user, decode_token

import socket
try:
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="fintrade_app")
except ImportError:
    geolocator = None

router = APIRouter(prefix="/device", tags=["Device Management"])

def extract_user_id(request: Request) -> int | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            return int(payload.get("sub"))
        except Exception:
            pass
    return None

@router.post("/register", response_model=schemas.SuccessResponse)
async def register_device(
    body: schemas.DeviceRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = extract_user_id(request)
    
    # Check if device already exists
    result = await db.execute(select(models.UserDevice).where(models.UserDevice.device_id == body.deviceId))
    device = result.scalar_one_or_none()
    
    if not device:
        device = models.UserDevice(device_id=body.deviceId)
        db.add(device)
    
    device.user_id = user_id
    device.device_name = body.deviceName
    device.manufacturer = body.manufacturer
    device.model = body.model
    device.platform = body.platform
    device.os_name = body.osName
    device.os_version = body.osVersion
    device.app_version = body.appVersion
    device.build_number = body.buildNumber
    device.language = body.language
    device.timezone = body.timezone
    device.screen_width = body.screenWidth
    device.screen_height = body.screenHeight
    device.fcm_token = body.fcmToken
    device.network_type = body.networkType
    device.battery_level = body.batteryLevel
    device.is_emulator = body.isEmulator
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    device.last_active = now
    if user_id:
        device.last_login = now
    
    await db.commit()
    
    return schemas.SuccessResponse(success=True, message="Device registered successfully")

@router.post("/location", response_model=schemas.SuccessResponse)
async def save_location(
    body: schemas.DeviceLocationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = extract_user_id(request)
    
    country, state, city, postal_code = None, None, None, None
    
    if body.permission.upper() == "GRANTED" and geolocator:
        try:
            location = geolocator.reverse(f"{body.latitude}, {body.longitude}", exactly_one=True)
            if location and location.raw.get('address'):
                addr = location.raw['address']
                country = addr.get('country')
                state = addr.get('state')
                city = addr.get('city') or addr.get('town') or addr.get('village')
                postal_code = addr.get('postcode')
        except Exception as e:
            pass
            
    google_maps_url = None
    if body.latitude and body.longitude:
        google_maps_url = f"https://maps.google.com/?q={body.latitude},{body.longitude}"
        
    client_ip = request.client.host if request.client else None
    if request.headers.get("x-forwarded-for"):
        client_ip = request.headers.get("x-forwarded-for").split(",")[0]
        
    user_location = models.UserLocation(
        user_id=user_id,
        latitude=body.latitude,
        longitude=body.longitude,
        permission_status=body.permission.upper(),
        country=country,
        state=state,
        city=city,
        postal_code=postal_code,
        google_maps_url=google_maps_url,
        public_ip=client_ip
    )
    
    db.add(user_location)
    await db.commit()
    
    return schemas.SuccessResponse(success=True, message="Location saved successfully")

@router.post("/notification", response_model=schemas.SuccessResponse)
async def save_notification_permission(
    body: schemas.DeviceNotificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = extract_user_id(request)
    
    # check existing permission for this user
    result = await db.execute(
        select(models.UserPermission)
        .where(models.UserPermission.user_id == user_id)
        .where(models.UserPermission.permission_type == "NOTIFICATION")
    )
    perm = result.scalar_one_or_none()
    
    if not perm:
        perm = models.UserPermission(
            user_id=user_id,
            permission_type="NOTIFICATION"
        )
        db.add(perm)
        
    perm.status = body.permission.upper()
    perm.fcm_token = body.fcmToken
    
    await db.commit()
    
    return schemas.SuccessResponse(success=True, message="Notification permission saved successfully")

@router.post("/contacts", response_model=schemas.SuccessResponse)
async def save_contacts_permission(
    body: schemas.DeviceContactsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = extract_user_id(request)
    
    # Save Permission
    result = await db.execute(
        select(models.UserPermission)
        .where(models.UserPermission.user_id == user_id)
        .where(models.UserPermission.permission_type == "CONTACTS")
    )
    perm = result.scalar_one_or_none()
    if not perm:
        perm = models.UserPermission(
            user_id=user_id,
            permission_type="CONTACTS"
        )
        db.add(perm)
    perm.status = body.permission.upper()
    
    # Save Contacts if GRANTED
    if body.permission.upper() == "GRANTED" and body.contacts:
        for contact in body.contacts:
            db_contact = models.UserContact(
                user_id=user_id,
                permission_status="GRANTED",
                contact_name=contact.name,
                mobile_number=contact.mobile,
                email=contact.email
            )
            db.add(db_contact)
            
    await db.commit()
    return schemas.SuccessResponse(success=True, message="Contacts saved successfully")

@router.post("/context", response_model=schemas.SuccessResponse)
async def save_context_permission(
    body: schemas.DeviceContextRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = extract_user_id(request)
    
    result = await db.execute(
        select(models.UserPermission)
        .where(models.UserPermission.user_id == user_id)
        .where(models.UserPermission.permission_type == "CONTEXT")
    )
    perm = result.scalar_one_or_none()
    
    if not perm:
        perm = models.UserPermission(
            user_id=user_id,
            permission_type="CONTEXT"
        )
        db.add(perm)
        
    perm.status = body.permission.upper()
    await db.commit()
    
    return schemas.SuccessResponse(success=True, message="Context permission saved successfully")

@router.get("/admin/list")
async def list_mobile_devices(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    platform: str = None,
    db: AsyncSession = Depends(get_db)
):
    # Verify Super Admin
    from app.core.security import require_roles
    admin = await require_roles(["super_admin"])(request=request, db=db)
    
    from sqlalchemy.orm import selectinload
    from sqlalchemy import func
    
    query = select(models.UserDevice).options(selectinload(models.UserDevice.user))
    
    if search:
        search_term = f"%{search}%"
        query = query.join(models.UserDevice.user, isouter=True).where(
            (models.UserDevice.device_name.ilike(search_term)) |
            (models.UserDevice.manufacturer.ilike(search_term)) |
            (models.UserDevice.model.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term))
        )
        
    if platform:
        query = query.where(models.UserDevice.platform.ilike(f"%{platform}%"))
        
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # Get paginated data
    query = query.order_by(models.UserDevice.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()
    
    # Fetch permissions and locations per user
    user_ids = [d.user_id for d in devices if d.user_id]
    
    perms_map = {}
    locs_map = {}
    if user_ids:
        # Permissions
        p_res = await db.execute(select(models.UserPermission).where(models.UserPermission.user_id.in_(user_ids)))
        for p in p_res.scalars().all():
            if p.user_id not in perms_map:
                perms_map[p.user_id] = {}
            perms_map[p.user_id][p.permission_type] = p.status
            
        # Locations (latest per user)
        l_res = await db.execute(
            select(models.UserLocation)
            .where(models.UserLocation.user_id.in_(user_ids))
            .order_by(models.UserLocation.created_at.desc())
        )
        for l in l_res.scalars().all():
            if l.user_id not in locs_map:
                locs_map[l.user_id] = l
                
    response_data = []
    for d in devices:
        user = d.user
        perms = perms_map.get(d.user_id, {})
        loc = locs_map.get(d.user_id)
        
        response_data.append({
            "id": d.id,
            "user_id": d.user_id,
            "user_name": user.full_name if user else None,
            "user_email": user.email if user else None,
            "user_phone": user.phone if user else None,
            "device_name": d.device_name,
            "manufacturer": d.manufacturer,
            "model": d.model,
            "platform": d.platform,
            "os_version": d.os_version,
            "app_version": d.app_version,
            "notification_permission": perms.get("NOTIFICATION", "NOT_ASKED"),
            "location_permission": perms.get("LOCATION", "NOT_ASKED"),
            "context_consent": perms.get("CONTEXT", "NOT_ASKED"),
            "country": loc.country if loc else None,
            "state": loc.state if loc else None,
            "city": loc.city if loc else None,
            "google_map_url": loc.google_maps_url if loc else None,
            "last_login": d.last_login,
            "last_active": d.last_active,
            "created_at": d.created_at
        })
        
    return {
        "total": total,
        "items": response_data
    }

users_router = APIRouter(prefix="/users", tags=["Users Export"])

@users_router.get("/export")
async def export_users(
    type: str = "excel",
    db: AsyncSession = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    import io
    import openpyxl
    
    # Query all users with devices, locations, permissions
    # Eager load the required data
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .options(selectinload(User.devices))
        .options(selectinload(User.permissions))
        .options(selectinload(User.locations))
    )
    users = result.scalars().unique().all()
    
    if type.lower() == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Users Data"
        
        # Headers
        headers = [
            "User ID", "Full Name", "Email", "Phone", "City", 
            "Device ID", "Device Platform", "OS Name", "App Version", 
            "FCM Token", "Location Permission", "Notification Permission",
            "Latest Latitude", "Latest Longitude", "Country", "State", "City"
        ]
        ws.append(headers)
        
        for user in users:
            device = user.devices[0] if user.devices else None
            loc_perm = next((p for p in user.permissions if p.permission_type == "LOCATION"), None)
            notif_perm = next((p for p in user.permissions if p.permission_type == "NOTIFICATION"), None)
            location = user.locations[0] if user.locations else None
            
            row = [
                user.id,
                user.full_name,
                user.email,
                user.phone,
                user.city,
                device.device_id if device else "",
                device.platform if device else "",
                device.os_name if device else "",
                device.app_version if device else "",
                device.fcm_token if device else "",
                loc_perm.status if loc_perm else "NOT_ASKED",
                notif_perm.status if notif_perm else "NOT_ASKED",
                location.latitude if location else "",
                location.longitude if location else "",
                location.country if location else "",
                location.state if location else "",
                location.city if location else ""
            ]
            ws.append(row)
            
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        
        return StreamingResponse(
            stream, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=users_export.xlsx"}
        )
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Unsupported export type. Use 'excel'.")
