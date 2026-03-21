"""工作台 API 测试：上下文树 + 考试仪表板。"""

import pytest
from sqlalchemy import select

from edu_cloud.models.user_role import UserRole
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult


@pytest.fixture
async def seed_exam_data(db, seed_teacher):
    """Create exam data for the teacher's school."""
    # Find the teacher's school from their role
    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()
    school_id = role.school_id

    # Create class group (use the same id referenced in teacher's class_ids)
    cls = ClassGroup(
        id="class-7-2", name="七年级2班", grade="七年级", school_id=school_id
    )
    db.add(cls)
    await db.flush()

    # Create students
    students = []
    for i in range(5):
        s = Student(
            name=f"学生{i}",
            student_number=f"S{i:03d}",
            school_id=school_id,
            class_id=cls.id,
            grade="七年级",
        )
        db.add(s)
        students.append(s)
    await db.flush()

    # Create exam
    exam = Exam(
        name="期中考试",
        subject_code="SX",
        subject_name="数学",
        max_score=150,
        school_id=school_id,
        semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    # Create results with varying scores
    scores = [120.0, 135.0, 90.0, 105.0, 145.0]
    for s, score in zip(students, scores):
        db.add(
            ExamResult(
                exam_id=exam.id,
                student_id=s.id,
                school_id=school_id,
                total_score=score,
            )
        )
    await db.commit()

    return {"exam_id": exam.id, "school_id": school_id, "class_id": cls.id}


@pytest.mark.asyncio
async def test_get_context_tree(client, teacher_headers):
    """GET /workspace/context returns classes and exams."""
    resp = await client.get("/api/v1/workspace/context", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "exams" in data
    assert "classes" in data
    assert isinstance(data["exams"], list)
    assert isinstance(data["classes"], list)


@pytest.mark.asyncio
async def test_get_context_tree_unauthorized(client):
    """GET /workspace/context without auth returns 403."""
    resp = await client.get("/api/v1/workspace/context")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_context_tree_with_data(client, teacher_headers, seed_exam_data):
    """GET /workspace/context returns seeded data."""
    resp = await client.get("/api/v1/workspace/context", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Teacher has class_ids=["class-7-2"], so only that class should appear
    assert len(data["classes"]) == 1
    assert data["classes"][0]["name"] == "七年级2班"
    # Exam should be visible
    assert len(data["exams"]) >= 1
    assert data["exams"][0]["name"] == "期中考试"


@pytest.mark.asyncio
async def test_get_exam_dashboard(client, teacher_headers, seed_exam_data):
    """GET /workspace/exams/{id}/dashboard returns stats + distribution."""
    exam_id = seed_exam_data["exam_id"]
    resp = await client.get(
        f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=teacher_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score_distribution" in data
    assert "stats" in data

    stats = data["stats"]
    assert stats["count"] == 5
    assert stats["avg"] == 119.0  # (120+135+90+105+145)/5 = 595/5 = 119
    assert stats["max"] == 145.0
    assert stats["min"] == 90.0
    assert stats["median"] == 120.0  # sorted: 90,105,120,135,145 → median=120

    # 6 distribution bins
    assert len(data["score_distribution"]) == 6


@pytest.mark.asyncio
async def test_get_exam_dashboard_empty(client, teacher_headers):
    """GET /workspace/exams/{nonexistent}/dashboard returns empty."""
    resp = await client.get(
        "/api/v1/workspace/exams/nonexistent/dashboard", headers=teacher_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"] == {}
    assert data["score_distribution"] == []


@pytest.mark.asyncio
async def test_get_exam_dashboard_admin(client, admin_headers, seed_exam_data):
    """Admin user (no school_id) gets empty dashboard gracefully."""
    exam_id = seed_exam_data["exam_id"]
    resp = await client.get(
        f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    # platform_admin has no school_id → empty result
    assert data["stats"] == {}
    assert data["score_distribution"] == []
