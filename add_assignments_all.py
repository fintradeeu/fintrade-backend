import re

with open('c:/work/fintrade/fintrade-backend/app/modules/courses/services.py', 'r', encoding='utf-8') as f:
    content = f.read()

get_all_func = '''
async def get_all_assignments(db: AsyncSession) -> List[Assignment]:
    result = await db.execute(select(Assignment))
    return result.scalars().all()
'''

if 'get_all_assignments' not in content:
    content = content.replace('async def get_course_assignments', get_all_func + '\nasync def get_course_assignments')
    with open('c:/work/fintrade/fintrade-backend/app/modules/courses/services.py', 'w', encoding='utf-8') as f:
        f.write(content)

with open('c:/work/fintrade/fintrade-backend/app/modules/admin/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

route_code = '''
@router.get("/assignments", response_model=List[course_schemas.AssignmentResponse])
async def list_all_assignments(
    _admin: User = Depends(require_roles(["admin", "faculty"])),
    db: AsyncSession = Depends(get_db),
):
    """List all assignments across all courses (admin/faculty only)."""
    assignments = await course_services.get_all_assignments(db)
    return [course_schemas.AssignmentResponse.model_validate(a) for a in assignments]
'''

if 'list_all_assignments' not in content:
    content = content.replace('@router.post("/assignments"', route_code + '\n@router.post("/assignments"')
    with open('c:/work/fintrade/fintrade-backend/app/modules/admin/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
print("Backend endpoints added")
