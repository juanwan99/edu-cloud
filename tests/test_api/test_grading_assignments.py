import pytest

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


@pytest.mark.asyncio
async def test_create_assignment(client, admin_headers, seed_school, db):
    school, _ = seed_school

    # Seed a teacher that belongs to the target school
    teacher = User(username="assign_teacher", display_name="分配教师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="subject_teacher",
                    school_id=school.id, is_primary=True))
    await db.commit()

    resp = await client.post(
        "/api/v1/grading/assignments",
        json={
            "exam_id": "fake-exam-id",
            "subject_id": "fake-subject-id",
            "question_ids": ["q1", "q2"],
            "teacher_id": str(teacher.id),
            "school_id": str(school.id),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["question_ids"] == ["q1", "q2"]


@pytest.mark.asyncio
async def test_list_assignments(client, admin_headers):
    resp = await client.get(
        "/api/v1/grading/assignments?exam_id=fake-exam-id",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_progress(client, admin_headers):
    resp = await client.get(
        "/api/v1/grading/progress/fake-exam-id",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_assignments" in data


@pytest.mark.asyncio
async def test_list_assignments_cross_school_rejected(client, admin_headers):
    """F-07: 跨校访问应返回空列表（school_id 过滤）"""
    resp = await client.get(
        "/api/v1/grading/assignments?exam_id=e1&school_id=wrong-school",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []
