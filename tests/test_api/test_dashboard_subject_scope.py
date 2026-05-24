import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.grading.models import GradingTask
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def dashboard_scope_data(db):
    school = School(name="Dashboard测试校", code="DS", district="D", api_key_hash="x")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="published")
    db.add(exam)
    await db.flush()

    math_subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    chinese_subj = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add_all([math_subj, chinese_subj])
    await db.flush()

    math_teacher = User(username="math_t_ds", display_name="数学老师")
    math_teacher.set_password("test123")
    db.add(math_teacher)
    await db.flush()

    t1 = GradingTask(school_id=school.id, subject_id=math_subj.id, status="pending", created_by=math_teacher.id)
    t2 = GradingTask(school_id=school.id, subject_id=chinese_subj.id, status="pending", created_by=math_teacher.id)
    db.add_all([t1, t2])
    await db.flush()

    db.add(UserRole(user_id=math_teacher.id, role="subject_teacher",
                    school_id=school.id, is_primary=True,
                    subject_codes=["math"], class_ids=["c1"]))
    await db.commit()

    token = create_access_token({
        "sub": math_teacher.id, "role": "subject_teacher",
        "school_id": school.id,
    })
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
        "math_subject_id": math_subj.id,
        "chinese_subject_id": chinese_subj.id,
    }


@pytest.mark.asyncio
async def test_dashboard_pending_grading_respects_subject_scope(client, dashboard_scope_data):
    """数学教师只应看到数学科目的待阅卷数=1，不包含语文的 pending。"""
    resp = await client.get("/api/v1/dashboard/summary",
                            headers=dashboard_scope_data["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_grading"] == 1, f"Expected 1 (math only), got {data['pending_grading']}"
    assert data["pending_subjects"] == 1, f"Expected 1 subject, got {data['pending_subjects']}"


@pytest.mark.asyncio
async def test_workspace_context_excludes_other_subjects(client, dashboard_scope_data):
    """数学教师的工作台上下文不应包含语文科目数据。"""
    resp = await client.get("/api/v1/workspace/context",
                            headers=dashboard_scope_data["headers"])
    assert resp.status_code == 200
    data = resp.json()
    all_codes = []
    for exam in data.get("exams", []):
        for subj in exam.get("subjects", []):
            all_codes.append(subj.get("code", subj.get("subject_code", "")))
        if exam.get("subject_code"):
            all_codes.append(exam["subject_code"])
    for code in all_codes:
        assert code != "chinese", "数学教师不应看到语文科目"


@pytest.mark.asyncio
async def test_grade_overview_excludes_other_subjects(client, dashboard_scope_data, db):
    """数学教师查看年级概览时，返回的科目数据不应包含语文。"""
    import sqlalchemy
    from edu_cloud.models.class_group import ClassGroup

    school_id = dashboard_scope_data["school_id"]
    cls = ClassGroup(name="初一1班", grade="初一", school_id=school_id, grade_id="g1")
    db.add(cls)
    await db.flush()

    from edu_cloud.modules.exam.models import Exam
    exam = (await db.execute(
        sqlalchemy.select(Exam).where(Exam.school_id == school_id)
    )).scalars().first()
    assert exam is not None, "Fixture 应创建考试"

    resp = await client.get(
        f"/api/v1/analytics/grade/g1/overview?exam_id={exam.id}",
        headers=dashboard_scope_data["headers"],
    )
    if resp.status_code == 404:
        pass  # grade 不存在是合法行为，不是安全问题
    elif resp.status_code == 200:
        data = resp.json()
        for cls_data in data.get("classes", []):
            for subj in cls_data.get("subjects", []):
                code = subj.get("subject_code", subj.get("code", ""))
                assert code != "chinese", "数学教师不应看到语文科目数据"
    else:
        pytest.fail(f"Unexpected status {resp.status_code}: {resp.text}")


@pytest.mark.asyncio
async def test_dashboard_grade_leader_counts_assigned_grade_only(client, db):
    """Grade leader with only grade_ids should see assigned-grade counts, not 0 or whole school."""
    school = School(name="年级范围校", code="GLDS", district="D", api_key_hash="x")
    db.add(school)
    await db.flush()

    grade7 = ClassGroup(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    grade8 = ClassGroup(name="八年级1班", grade="八年级", grade_number=8, school_id=school.id)
    db.add_all([grade7, grade8])
    await db.flush()

    from edu_cloud.models.student import Student
    db.add_all([
        Student(name="七年级学生", student_number="GL001", class_id=grade7.id, school_id=school.id, grade="七年级"),
        Student(name="八年级学生", student_number="GL002", class_id=grade8.id, school_id=school.id, grade="八年级"),
    ])
    await db.flush()

    user = User(username="grade_leader_dash", display_name="年级组长")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    role = UserRole(user_id=user.id, role="grade_leader", school_id=school.id, grade_ids=["7"], is_primary=True)
    db.add(role)
    await db.commit()

    token = create_access_token({
        "sub": user.id,
        "role": "grade_leader",
        "school_id": school.id,
        "active_role_id": role.id,
    })

    resp = await client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_classes"] == 1
    assert data["total_students"] == 1
