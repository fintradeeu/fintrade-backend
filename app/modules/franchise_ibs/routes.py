"""Franchise IBs module — API Routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from datetime import datetime, timezone, timedelta

from app.db.database import get_db
from app.core.security import get_current_user
from app.modules.auth.models import User, Role
from app.modules.franchise_ibs import schemas
from app.modules.franchise_ibs.models import FranchiseIB
from app.modules.distributors.models import Distributor
from app.modules.auth.schemas import MessageResponse

from app.modules.franchise_ibs import schemas, services
from app.modules.distributors.schemas import ManualStudentRegisterRequest

router = APIRouter(prefix="/franchise-ibs", tags=["Franchise IBs"])


@router.post("/", response_model=schemas.FranchiseIBResponse)
async def register_franchise_ib(
    data: schemas.FranchiseIBCreate,
    db: AsyncSession = Depends(get_db),
    # Uncomment to require super_admin to create:
    # current_user: User = Depends(get_current_user) 
):
    """Register a new Franchise IB."""
    try:
        profile = await services.create_franchise_ib(db, data, created_by_admin=False)
        await db.commit()
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard", response_model=schemas.FranchiseIBDashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics for the logged-in Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    stats = await services.get_dashboard_stats(db, profile.id)
    return stats


@router.get("/ibs")
async def get_franchise_ibs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all IBs (Distributors) under the current Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    
    # Fetch IBs
    stmt = select(Distributor, User).join(User, User.id == Distributor.user_id).where(Distributor.franchise_id == profile.id)
    result = await db.execute(stmt)
    ibs = []
    for dist, user in result.all():
        ibs.append({
            "id": dist.id,
            "referral_code": dist.referral_code,
            "region": dist.region,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "created_at": dist.created_at
        })
    return {"status": "success", "data": ibs}


@router.get("/students")
async def get_franchise_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all students and their journey timeline under the current Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
    
    from app.modules.distributors.services import list_referral_journeys
    journeys = await list_referral_journeys(db, franchise_ib_id=profile.id)
    
    return {"status": "success", "data": journeys}


@router.post("/manual-register", status_code=201)
async def manual_register_student(
    body: ManualStudentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually register a student and optionally record offline payment."""
    from app.modules.distributors.services import manual_register_student as _manual_register
    
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    return await _manual_register(db, data=body, franchise_ib_id=profile.id)


@router.put("/students/{student_id}", response_model=MessageResponse)
async def update_franchise_student(
    student_id: int,
    body: schemas.StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update details of a student registered under the Franchise IB."""
    profile = await services.get_franchise_ib_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Franchise IB profile not found")
        
    # Check if student is referred by this Franchise IB
    from app.modules.distributors.models import StudentReferral
    from app.modules.auth.models import User
    
    stmt = select(StudentReferral).where(
        StudentReferral.student_id == student_id,
        StudentReferral.franchise_ib_id == profile.id
    )
    res = await db.execute(stmt)
    referral = res.scalar_one_or_none()
    if not referral:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this student's details"
        )
        
    # Fetch the student user
    student = await db.get(User, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    # Update fields
    if body.full_name is not None:
        student.full_name = body.full_name
    if body.phone is not None:
        # Check if phone number is already taken by another user
        if body.phone != student.phone:
            dup = await db.execute(select(User).where(User.phone == body.phone))
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Phone number already registered by another user")
        student.phone = body.phone
    if body.city is not None:
        student.city = body.city
        
    await db.commit()
    return MessageResponse(message="Student details updated successfully")


