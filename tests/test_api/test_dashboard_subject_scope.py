import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
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
