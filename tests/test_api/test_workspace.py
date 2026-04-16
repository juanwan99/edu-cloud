"""工作台 API 测试：上下文树 + 考试仪表板。"""

import pytest
from sqlalchemy import select

from edu_cloud.models.user_role import UserRole
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult


@pytest.fixture
async def seed_exam_data(db, seed_teacher):
    """Create exam data for the teacher's school.

    Includes an out-of-scope class (七年级3班) to verify scope filtering.
    Teacher only has class_ids=["class-7-2"], so class-7-3 should be excluded.
    """
    # Find the teacher's school from their role
    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()
    school_id = role.school_id

    # Create in-scope class (teacher's class_ids=["class-7-2"])
    cls = ClassGroup(
        id="class-7-2", name="七年级2班", grade="七年级", school_id=school_id
    )
    db.add(cls)

    # TG-01: Create out-of-scope class in the same school
    cls_out = ClassGroup(
        id="class-7-3", name="七年级3班", grade="七年级", school_id=school_id
    )
    db.add(cls_out)
    await db.flush()

    # Create in-scope students
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

    # TG-01: Create out-of-scope students
    out_students = []
    for i in range(2):
        s = Student(
            name=f"外班学生{i}",
            student_number=f"OUT{i:03d}",
            school_id=school_id,
            class_id=cls_out.id,
            grade="七年级",
        )
        db.add(s)
        out_students.append(s)
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

    # Create results for in-scope students
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

    # TG-01: Create results for out-of-scope students
    out_scores = [80.0, 60.0]
    for s, score in zip(out_students, out_scores):
        db.add(
            ExamResult(
                exam_id=exam.id,
                student_id=s.id,
                school_id=school_id,
                total_score=score,
            )
        )
    await db.commit()

    return {
        "exam_id": exam.id,
        "school_id": school_id,
        "class_id": cls.id,
        "out_class_id": cls_out.id,
    }


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
async def test_get_context_tree_returns_status_field(
    client, teacher_headers, seed_exam_data
):
    """F010 回归：workspace/context 返回的每个 exam 必须含 `status` 字段。

    前端 ContextPanel 之前绑 `e.subject_code`（legacy NULL），修复后应绑
    `e.status`。后端 workspace_service 必须暴露 status 字段。

    反例：错误实现只返回 {id, name, subject_code, semester}，
    前端模板字符串得到 "(null)"。
    """
    resp = await client.get("/api/v1/workspace/context", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["exams"]) >= 1
    exam = data["exams"][0]
    assert "status" in exam, f"exam 响应必须含 status 字段，实际: {list(exam.keys())}"
    # seed_exam_data 没设 status → default 'draft'
    assert exam["status"] == "draft", f"default status 应为 'draft'，实际: {exam['status']}"


@pytest.mark.asyncio
async def test_get_context_tree_with_data(client, teacher_headers, seed_exam_data):
    """GET /workspace/context returns only in-scope class, excludes out-of-scope.

    TG-01: seed_exam_data creates both class-7-2 (in scope) and class-7-3
    (out of scope). The teacher has class_ids=["class-7-2"], so class-7-3
    must NOT appear. Without the out-of-scope class, this test would pass
    even if scope filtering were broken.
    """
    resp = await client.get("/api/v1/workspace/context", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Teacher has class_ids=["class-7-2"], so only that class should appear
    assert len(data["classes"]) == 1
    assert data["classes"][0]["name"] == "七年级2班"
    # Verify out-of-scope class is NOT present
    class_names = [c["name"] for c in data["classes"]]
    assert "七年级3班" not in class_names
    # Exam should be visible
    assert len(data["exams"]) >= 1
    assert data["exams"][0]["name"] == "期中考试"


@pytest.mark.asyncio
async def test_get_exam_dashboard(client, teacher_headers, seed_exam_data):
    """GET /workspace/exams/{id}/dashboard returns only in-scope student scores.

    TG-01: seed_exam_data creates 5 in-scope students (scores: 120,135,90,105,145)
    and 2 out-of-scope students (scores: 80,60). Dashboard must only count the
    in-scope 5, not all 7. If scope filtering were broken, count would be 7 and
    avg would be ~105 instead of 119.
    """
    exam_id = seed_exam_data["exam_id"]
    resp = await client.get(
        f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=teacher_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score_distribution" in data
    assert "stats" in data

    stats = data["stats"]
    # Must be 5 (in-scope only), NOT 7 (all students)
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


# --- TG-02: Dashboard edge case tests ---


@pytest.fixture
async def seed_single_score(db, seed_teacher):
    """Create exam data with exactly 1 student and 1 score."""
    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()
    school_id = role.school_id

    cls = ClassGroup(
        id="class-7-2", name="七年级2班", grade="七年级", school_id=school_id
    )
    db.add(cls)
    await db.flush()

    student = Student(
        name="独生学生",
        student_number="SOLO001",
        school_id=school_id,
        class_id=cls.id,
        grade="七年级",
    )
    db.add(student)
    await db.flush()

    exam = Exam(
        name="单人考试",
        subject_code="YW",
        subject_name="语文",
        max_score=150,
        school_id=school_id,
        semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    db.add(
        ExamResult(
            exam_id=exam.id,
            student_id=student.id,
            school_id=school_id,
            total_score=88.5,
        )
    )
    await db.commit()

    return {"exam_id": exam.id}


@pytest.mark.asyncio
async def test_dashboard_single_score(client, teacher_headers, seed_single_score):
    """TG-02: Single score — median/avg/max/min should all equal the same value."""
    exam_id = seed_single_score["exam_id"]
    resp = await client.get(
        f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=teacher_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    stats = data["stats"]

    assert stats["count"] == 1
    assert stats["avg"] == 88.5
    assert stats["max"] == 88.5
    assert stats["min"] == 88.5
    assert stats["median"] == 88.5


@pytest.fixture
async def seed_all_max_scores(db, seed_teacher):
    """Create exam data where all students score max_score (150)."""
    role = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == seed_teacher.id)
        )
    ).scalar_one()
    school_id = role.school_id

    cls = ClassGroup(
        id="class-7-2", name="七年级2班", grade="七年级", school_id=school_id
    )
    db.add(cls)
    await db.flush()

    exam = Exam(
        name="满分考试",
        subject_code="YY",
        subject_name="英语",
        max_score=150,
        school_id=school_id,
        semester="2025-2026-2",
    )
    db.add(exam)
    await db.flush()

    for i in range(4):
        s = Student(
            name=f"满分学生{i}",
            student_number=f"MAX{i:03d}",
            school_id=school_id,
            class_id=cls.id,
            grade="七年级",
        )
        db.add(s)
        await db.flush()
        db.add(
            ExamResult(
                exam_id=exam.id,
                student_id=s.id,
                school_id=school_id,
                total_score=150.0,
            )
        )
    await db.commit()

    return {"exam_id": exam.id}


@pytest.mark.asyncio
async def test_dashboard_all_max_scores(client, teacher_headers, seed_all_max_scores):
    """TG-02: All scores = max_score (150) — only 90%+ bin should have counts."""
    exam_id = seed_all_max_scores["exam_id"]
    resp = await client.get(
        f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=teacher_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    stats = data["stats"]

    assert stats["count"] == 4
    assert stats["avg"] == 150.0
    assert stats["max"] == 150.0
    assert stats["min"] == 150.0
    assert stats["median"] == 150.0

    # All 4 scores are 150 (= max_score), should be in "90%+" bin only
    dist = {d["range"]: d["count"] for d in data["score_distribution"]}
    assert dist["90%+"] == 4
    # All other bins should be 0
    for label in ["<40%", "40-59%", "60-69%", "70-79%", "80-89%"]:
        assert dist[label] == 0, f"Expected 0 in {label} bin, got {dist[label]}"


@pytest.mark.asyncio
async def test_workspace_denied_for_parent(client, db):
    """Parent role (VIEW_SCORES only) should be denied access to workspace endpoints.

    R2-01: workspace endpoints require VIEW_EXAMS. parent only has VIEW_SCORES,
    so both /context and /exams/{id}/dashboard must return 403.
    """
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    # Create parent user
    user = User(username="parent1", display_name="家长")
    user.set_password("123456")
    db.add(user)
    await db.flush()

    school = School(
        name="测试校P", code="TESTP", district="测试区", api_key_hash="x"
    )
    db.add(school)
    await db.flush()

    db.add(
        UserRole(
            user_id=user.id, role="parent", school_id=school.id, is_primary=True
        )
    )
    await db.commit()

    # Login as parent
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "parent1", "password": "123456"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Both workspace endpoints must return 403 for parent role
    resp = await client.get("/api/v1/workspace/context", headers=headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/workspace/exams/fake-id/dashboard", headers=headers)
    assert resp.status_code == 403
