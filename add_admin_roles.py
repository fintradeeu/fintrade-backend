import re

with open('c:/work/fintrade/fintrade-backend/app/modules/admin/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

mock_routes = '''
# In-memory mock for Admin Roles
mock_admins = [
    {
      "id": 1,
      "name": "Rajesh Mehta",
      "email": "rajesh.mehta@fintrade.in",
      "role": "Super Admin",
      "status": "Active",
      "permissions": {
        "manageCourses": True,
        "manageStudents": True,
        "managePayments": True,
        "manageContent": True,
        "manageExams": True,
        "manageAdmins": True,
        "canViewRevenue": True,
      },
      "lastActive": "2026-04-16"
    }
]

@router.get("/roles")
async def get_admin_roles(_admin: User = Depends(require_roles(["admin"]))):
    return mock_admins

@router.post("/roles")
async def create_admin_role(data: dict, _admin: User = Depends(require_roles(["admin"]))):
    data["id"] = len(mock_admins) + 1
    mock_admins.append(data)
    return data

@router.put("/roles/{role_id}")
async def update_admin_role(role_id: int, data: dict, _admin: User = Depends(require_roles(["admin"]))):
    for i, a in enumerate(mock_admins):
        if a["id"] == role_id:
            data["id"] = role_id
            mock_admins[i] = data
            return data
    return {"error": "Not found"}

@router.delete("/roles/{role_id}")
async def delete_admin_role(role_id: int, _admin: User = Depends(require_roles(["admin"]))):
    global mock_admins
    mock_admins = [a for a in mock_admins if a["id"] != role_id]
    return {"success": True}
'''

if '/roles' not in content:
    content = content + '\n' + mock_routes
    with open('c:/work/fintrade/fintrade-backend/app/modules/admin/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
print("Admin roles mock endpoints added")
