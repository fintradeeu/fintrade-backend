"""Mobile API Integration — routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.modules.auth.models import User, Role, Student
from app.modules.courses.models import CourseEnrollment
from app.modules.mobile_api import schemas

router = APIRouter(prefix="/users", tags=["Mobile API"])

@router.post("", response_model=schemas.MobileUserCreateResponse, status_code=201)
async def create_mobile_user(
    body: schemas.MobileUserCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user or update details if already exists by email."""
    email = body.email.strip().lower()
    first_name = body.first_name.strip()
    last_name = body.last_name.strip()
    phone = body.phone.strip()
    full_name = f"{first_name} {last_name}".strip()

    # Check if user already exists
    existing_user = await db.scalar(
        select(User).where(User.email == email)
    )
    if existing_user:
        # Update details
        existing_user.full_name = full_name
        existing_user.phone = phone
        await db.commit()
        return schemas.MobileUserCreateResponse(
            success=True,
            user_id=str(existing_user.id),
            message="User updated successfully"
        )

    # Create new user
    new_user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return schemas.MobileUserCreateResponse(
        success=True,
        user_id=str(new_user.id),
        message="User created successfully"
    )

@router.get("/{user_id}", response_model=schemas.MobileUserGetResponse)
async def get_mobile_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve user details by user ID and split full_name into first/last name."""
    try:
        u_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await db.get(User, u_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    parts = (user.full_name or "").split(" ", 1)
    first_name = parts[0] if len(parts) > 0 else ""
    last_name = parts[1] if len(parts) > 1 else ""

    data = schemas.UserDetails(
        first_name=first_name,
        last_name=last_name,
        email=user.email,
        phone=user.phone
    )

    return schemas.MobileUserGetResponse(
        success=True,
        data=data
    )

# Student registration endpoint mounted on the same router (or we can route it separately in main.py)
# Since the router prefix is `/users`, we can also define `/students` by using a separate APIRouter
# or registering it with absolute path in the APIRouter.
# Wait, let's create a separate student router or register students prefix on a second router!
# A second router is cleaner so that the prefix doesn't conflict.
student_router = APIRouter(prefix="/students", tags=["Mobile API"])

@student_router.post("", response_model=schemas.MobileStudentCreateResponse, status_code=201)
async def create_mobile_student(
    body: schemas.MobileStudentCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a student profile linked to a user, assign the student role, and enroll them."""
    try:
        u_id = int(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    try:
        c_id = int(body.course_id) if body.course_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid course ID format")

    # Fetch User
    user = await db.get(User, u_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Add the student role if not already assigned
    student_role = await db.scalar(
        select(Role).where(Role.name == "student")
    )
    if student_role and student_role not in user.roles:
        user.roles.append(student_role)

    # Check if Student profile already exists
    student = await db.scalar(
        select(Student).where(Student.user_id == u_id)
    )
    if student:
        # Update details
        student.course_id = c_id
        student.address = body.address
        student.qualification = body.qualification
    else:
        # Create student profile
        student = Student(
            user_id=u_id,
            course_id=c_id,
            address=body.address,
            qualification=body.qualification
        )
        db.add(student)

    # Automatically enroll the user in the course if course_id is provided
    if c_id:
        existing_enrollment = await db.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == u_id,
                CourseEnrollment.course_id == c_id
            )
        )
        if not existing_enrollment:
            enrollment = CourseEnrollment(
                user_id=u_id,
                course_id=c_id,
                is_active=True,
                progress_percent=0.0
            )
            db.add(enrollment)

    await db.commit()
    # Refresh student to get final ID
    await db.refresh(student)

    return schemas.MobileStudentCreateResponse(
        success=True,
        student_id=str(student.id),
        message="Student created successfully"
    )
