import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def admin_token(db):
    school = School(name="Test School", code="CRUD01")
    db.add(school)
    await db.commit()
    user = User(username="admin_crud", display_name="Admin")
    user.set_password("x")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    return token, school.id


async def test_list_schools(client, admin_token):
    token, _ = admin_token
    resp = await client.get("/api/v1/schools", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_create_school(client, admin_token):
    token, _ = admin_token
    resp = await client.post("/api/v1/schools", json={
        "name": "New School",
        "code": "NS001",
        "district": "测试区",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "New School"
