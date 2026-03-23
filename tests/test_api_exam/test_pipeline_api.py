"""B2-03: DF-001 auto-trigger + pipeline API tests."""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.student import Class, Student
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.profile.models import StudentExamSnapshot
from sqlalchemy import select, func


async def _setup_completed_exam(db):
    """创建一个 reviewing 状态的考试（可转 completed），含学生答题数据。"""
    school = School(name="测试", code="PIPE01")
    db.add(school)
    await db.flush()

    cls = Class(name="班级", grade="高二", school_id=school.id)
    db.add(cls)
    await db.flush()

    stu = Student(name="学生1", student_number="PIPE001", class_id=cls.id, school_id=school.id)
    db.add(stu)
    await db.flush()

    admin = User(username="pipeadmin", display_name="管理员")
    admin.set_password("123456")
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    teacher = User(username="pipeteacher", display_name="教师")
    teacher.set_password("123456")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="考试", card_title="考试", school_id=school.id, status="reviewing")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    db.add(q)
    await db.flush()

    db.add(StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id=stu.id,
        question_id=q.id, school_id=school.id, score=7.0,
    ))
    await db.commit()
    return school, exam


async def _login(client, username="pipeadmin"):
    resp = await client.post("/api/v1/auth/login", json={
        "username": username, "password": "123456",
    })
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_pipeline_api_admin_triggers(client, db):
    """B2-03: POST /api/pipeline/run/{exam_id} admin 可触发。"""
    school, exam = await _setup_completed_exam(db)
    token = await _login(client, "pipeadmin")
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.post(f"/api/v1/pipeline/run/{exam.id}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "bank_questions" in data
    assert "exam_snapshots" in data
    assert "error_patterns" in data


@pytest.mark.asyncio
async def test_pipeline_api_teacher_forbidden(client, db):
    """B2-03: POST /api/pipeline/run/{exam_id} teacher 被拒。"""
    school, exam = await _setup_completed_exam(db)
    token = await _login(client, "pipeteacher")
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.post(f"/api/v1/pipeline/run/{exam.id}", headers=h)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_exam_status_completed_auto_triggers_pipeline(client, db):
    """B2-03: PATCH exam status → completed 自动触发 pipeline (DF-001)。"""
    school, exam = await _setup_completed_exam(db)
    token = await _login(client, "pipeadmin")
    h = {"Authorization": f"Bearer {token}"}

    # 转 completed
    resp = await client.patch(f"/api/v1/exams/{exam.id}", headers=h, json={"status": "completed"})
    assert resp.status_code == 200

    # 验证 pipeline 自动触发：应有 snapshot 生成
    count = await db.execute(
        select(func.count()).select_from(StudentExamSnapshot)
        .where(StudentExamSnapshot.exam_id == exam.id)
    )
    assert count.scalar() >= 1  # DF-001: auto-trigger 已生效
