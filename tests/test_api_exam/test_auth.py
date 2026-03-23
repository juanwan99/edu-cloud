import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


async def test_login_success(client, db):
    school = School(name="S1", code="AUTH01")
    db.add(school)
    await db.commit()

    user = User(username="admin1", display_name="Admin")
    user.set_password("pass123")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    resp = await client.post("/api/v1/auth/login", json={
        "school_code": "AUTH01",
        "username": "admin1",
        "password": "pass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"


async def test_login_wrong_password(client, db):
    school = School(name="S2", code="AUTH02")
    db.add(school)
    await db.commit()

    user = User(username="admin2", display_name="Admin")
    user.set_password("correct")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    resp = await client.post("/api/v1/auth/login", json={
        "school_code": "AUTH02",
        "username": "admin2",
        "password": "wrong",
    })
    assert resp.status_code == 401


async def test_login_nonexistent_user(client, db):
    """Login with nonexistent username → 401."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "nonexistent",
        "password": "pass",
    })
    assert resp.status_code == 401
