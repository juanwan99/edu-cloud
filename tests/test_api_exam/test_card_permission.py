import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def teacher_user(db):
    user = User(username="card_perm_teacher", display_name="Card Test Teacher")
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
async def test_save_layout_requires_manage_exams(client, teacher_headers):
    resp = await client.put(
        "/api/v1/card/editor-layout/fake-subject-id",
        json={"layout": {}},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_publish_card_requires_manage_exams(client, teacher_headers):
    resp = await client.post(
        "/api/v1/card/publish",
        json={"subject_id": "fake", "exam_id": "fake", "html": "<html></html>"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_pdf_requires_manage_exams(client, teacher_headers):
    resp = await client.post(
        "/api/v1/card/export/pdf",
        json={"html": "<html></html>"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_skeleton_requires_manage_exams(client, teacher_headers):
    resp = await client.delete(
        "/api/v1/card/skeleton/fake-id",
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_card_read(client, admin_headers):
    resp = await client.get(
        "/api/v1/card/editor-layout/fake-subject-id",
        headers=admin_headers,
    )
    assert resp.status_code != 403
