import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def auth_and_exam(client, db):
    school = School(name="Test School", code="SU01")
    db.add(school)
    await db.commit()
    user = User(username="teacher", display_name="T")
    user.set_password("pass")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/exams", json={"name": "期中", "card_title": "期中考试答题卡"}, headers=headers)
    exam_id = resp.json()["id"]
    return headers, school.id, exam_id


async def test_create_subject(client, auth_and_exam):
    headers, school_id, exam_id = auth_and_exam
    resp = await client.post(
        f"/api/v1/exams/{exam_id}/subjects",
        json={"name": "数学", "code": "math"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "数学"
    assert data["code"] == "math"
    assert data["exam_id"] == exam_id


async def test_list_subjects(client, auth_and_exam):
    headers, _, exam_id = auth_and_exam
    await client.post(f"/api/v1/exams/{exam_id}/subjects", json={"name": "语文", "code": "chinese"}, headers=headers)
    resp = await client.get(f"/api/v1/exams/{exam_id}/subjects", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_create_subject_duplicate_code(client, auth_and_exam):
    headers, _, exam_id = auth_and_exam
    await client.post(f"/api/v1/exams/{exam_id}/subjects", json={"name": "数学", "code": "math"}, headers=headers)
    resp = await client.post(f"/api/v1/exams/{exam_id}/subjects", json={"name": "数学2", "code": "math"}, headers=headers)
    assert resp.status_code == 409


async def test_create_subject_exam_not_found(client, auth_and_exam):
    headers, _, _ = auth_and_exam
    resp = await client.post(
        "/api/v1/exams/nonexistent/subjects",
        json={"name": "数学", "code": "math"},
        headers=headers,
    )
    assert resp.status_code == 404
