import pytest


@pytest.mark.asyncio
async def test_create_assignment(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        "/api/v1/grading/assignments",
        json={
            "exam_id": "fake-exam-id",
            "subject_id": "fake-subject-id",
            "question_ids": ["q1", "q2"],
            "teacher_id": "fake-teacher-id",
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
