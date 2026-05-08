import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def teacher_user(db):
    user = User(username="teacher_perm_test", display_name="Test Teacher")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="subject_teacher", is_primary=True))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def teacher_headers(teacher_user):
    token = create_access_token({"sub": teacher_user.id, "role": "subject_teacher"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_teacher_requires_permission(client, teacher_headers):
    resp = await client.post(
        "/api/v1/teachers",
        json={"username": "newteacher", "display_name": "新教师", "password": "Test1234!"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_teacher_requires_permission(client, teacher_headers):
    resp = await client.delete(
        "/api/v1/teachers/fake-id",
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_teachers_requires_permission(client, teacher_headers):
    resp = await client.post(
        "/api/v1/teachers/import",
        files={"file": ("teachers.xlsx", b"fake", "application/octet-stream")},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_teacher(client, admin_headers):
    resp = await client.post(
        "/api/v1/teachers",
        json={"username": "newteacher2", "display_name": "新教师2", "password": "Test1234!"},
        headers=admin_headers,
    )
    assert resp.status_code != 403
