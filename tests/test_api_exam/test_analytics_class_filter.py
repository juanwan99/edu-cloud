"""B2: analytics 端点必须按 class_ids 过滤学生成绩。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.student import Class, Student
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def class_filter_setup(client, db):
    """2 classes, teacher sees only c1."""
    school = School(id="cf_s", name="CF", code="CF01")
    db.add(school)
    await db.commit()

    c1 = Class(id="cf_c1", name="1班", grade="高二", school_id="cf_s")
    c2 = Class(id="cf_c2", name="2班", grade="高二", school_id="cf_s")
    db.add_all([c1, c2])
    await db.commit()

    # head_teacher: class_ids=["cf_c1"], sees all subjects but only c1
    teacher = User(id="cf_ht", username="ht", display_name="班主任")
    teacher.set_password("p")
    admin = User(id="cf_admin", username="cfadmin", display_name="管理员")
    admin.set_password("p")
    db.add_all([teacher, admin])
    await db.commit()
    db.add_all([
        UserRole(user_id="cf_ht", role="head_teacher", school_id="cf_s", is_primary=True, class_ids=["cf_c1"]),
        UserRole(user_id="cf_admin", role="admin", school_id="cf_s", is_primary=True),
    ])
    await db.flush()

    exam = Exam(id="cf_exam", name="考试", school_id="cf_s")
    db.add(exam)
    await db.commit()

    subj = Subject(id="cf_subj", exam_id="cf_exam", name="语文", code="YW", school_id="cf_s")
    db.add(subj)
    await db.commit()

    q = Question(id="cf_q1", subject_id="cf_subj", name="Q1",
                 question_type="essay", max_score=10.0, school_id="cf_s")
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id="cf_subj", school_id="cf_s",
        status="completed", total=2, completed=2, failed=0, created_by="cf_admin",
    )
    db.add(task)
    await db.commit()

    # s1 in c1, s2 in c2
    s1 = Student(id="cf_s1", name="张三", student_number="CF001", class_id="cf_c1", school_id="cf_s")
    s2 = Student(id="cf_s2", name="李四", student_number="CF002", class_id="cf_c2", school_id="cf_s")
    db.add_all([s1, s2])
    await db.commit()

    for sid, score in [("cf_s1", 8.0), ("cf_s2", 6.0)]:
        a = StudentAnswer(
            exam_id="cf_exam", subject_id="cf_subj", student_id=sid,
            question_id="cf_q1", image_path=f"/fake/{sid}.png", school_id="cf_s",
        )
        db.add(a)
        await db.commit()
        r = GradingResult(
            ai_task_id=task.id, answer_id=a.id, question_id="cf_q1",
            school_id="cf_s", ai_score=score, final_score=score, max_score=10.0,
            ai_feedback="f", ai_confidence=0.9, status="ai_done",
        )
        db.add(r)
        await db.commit()

    return {
        "teacher_headers": {"Authorization": f"Bearer {create_access_token({'sub': 'cf_ht', 'school_id': 'cf_s', 'role': 'head_teacher'})}"},
        "admin_headers": {"Authorization": f"Bearer {create_access_token({'sub': 'cf_admin', 'school_id': 'cf_s', 'role': 'admin'})}"},
    }


async def test_admin_summary_sees_all(client, class_filter_setup):
    """Admin should see both students."""
    resp = await client.get(
        "/api/v1/analytics/exam/cf_exam/summary",
        headers=class_filter_setup["admin_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total_students"] == 2


async def test_teacher_summary_only_own_class(client, class_filter_setup):
    """Head teacher with class_ids=[cf_c1] should only see cf_s1's score."""
    resp = await client.get(
        "/api/v1/analytics/exam/cf_exam/summary",
        headers=class_filter_setup["teacher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 1
    subj = data["subjects"][0]
    assert subj["avg_score"] == 8.0  # only cf_s1
    assert subj["graded_count"] == 1


async def test_teacher_distribution_filtered(client, class_filter_setup):
    """Distribution should also respect class filter."""
    resp = await client.get(
        "/api/v1/analytics/exam/cf_exam/distribution",
        headers=class_filter_setup["teacher_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total_students"] == 1


async def test_teacher_question_analysis_filtered(client, class_filter_setup):
    """Question analysis should also respect class filter."""
    resp = await client.get(
        "/api/v1/analytics/subject/cf_subj/questions",
        headers=class_filter_setup["teacher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Only cf_s1's score (8.0) should be included
    assert data["questions"][0]["graded_count"] == 1
    assert data["questions"][0]["avg_score"] == 8.0
