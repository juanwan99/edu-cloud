import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="ranking_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_two_exams(db, seed_school):
    """Seed two exams for delta calculation."""
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    stu1 = Student(name="张三", student_number="R001", class_id=cls.id, school_id=school.id, grade="高一")
    stu2 = Student(name="李四", student_number="R002", class_id=cls.id, school_id=school.id, grade="高一")
    stu3 = Student(name="王五", student_number="R003", class_id=cls.id, school_id=school.id, grade="高一")
    db.add_all([stu1, stu2, stu3])
    await db.flush()

    from datetime import date
    exam1 = Exam(name="期中", status="completed", exam_date=date(2026, 3, 1), school_id=school.id)
    exam2 = Exam(name="期末", status="completed", exam_date=date(2026, 6, 1), school_id=school.id)
    db.add_all([exam1, exam2])
    await db.flush()

    for exam, scores_map in [
        (exam1, {stu1.id: 90, stu2.id: 80, stu3.id: 70}),
        (exam2, {stu1.id: 75, stu2.id: 85, stu3.id: 95}),
    ]:
        subj = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
        db.add(subj)
        await db.flush()
        q = Question(name="1", question_type="choice", max_score=100, subject_id=subj.id, school_id=school.id)
        db.add(q)
        await db.flush()
        for sid, score in scores_map.items():
            sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=sid, question_id=q.id, school_id=school.id)
            db.add(sa)
            await db.flush()
            gr = GradingResult(answer_id=sa.id, question_id=q.id, school_id=school.id,
                               final_score=float(score), max_score=100, status="confirmed", source="manual")
            db.add(gr)
        await db.commit()

    return exam1, exam2, cls, [stu1, stu2, stu3]


@pytest.mark.asyncio
async def test_student_rankings_with_delta(client, school_admin_headers, seed_school, db):
    exam1, exam2, _, students = await _seed_two_exams(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam2.id}/student-rankings",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["students"]) == 3

    # exam2: 王五95>#1, 李四85>#2, 张三75>#3
    # exam1: 张三90>#1, 李四80>#2, 王五70>#3
    ww = next(s for s in data["students"] if s["name"] == "王五")
    assert ww["grade_rank"] == 1
    assert ww["delta_grade"] == 2  # 从 #3 → #1，进步 2 名

    zs = next(s for s in data["students"] if s["name"] == "张三")
    assert zs["grade_rank"] == 3
    assert zs["delta_grade"] == -2  # 从 #1 → #3，退步 2 名


@pytest.mark.asyncio
async def test_critical_students(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    cls = Class(name="高一(2)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()
    # 3 学生：58 分（差 2 分及格）、61 分（及格）、84 分（差 1 分优秀）
    students_data = [("临界A", "C001", 58), ("及格B", "C002", 61), ("临界C", "C003", 84)]
    stu_objs = []
    for name, num, _ in students_data:
        s = Student(name=name, student_number=num, class_id=cls.id, school_id=school.id, grade="高一")
        db.add(s)
        stu_objs.append(s)
    await db.flush()

    exam = Exam(name="临界测试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(name="语文", code="chinese", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="essay", max_score=100, subject_id=subj.id, school_id=school.id)
    db.add(q)
    await db.flush()

    for stu, (_, _, score) in zip(stu_objs, students_data):
        sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
        db.add(sa)
        await db.flush()
        gr = GradingResult(answer_id=sa.id, question_id=q.id, school_id=school.id,
                           final_score=float(score), max_score=100, status="confirmed", source="manual")
        db.add(gr)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/critical-students",
        params={"threshold": "3"},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["near_pass"]) == 1
    assert data["near_pass"][0]["name"] == "临界A"
    assert data["near_pass"][0]["gap"] == 2.0
    assert len(data["near_excellent"]) == 1
    assert data["near_excellent"][0]["name"] == "临界C"


@pytest.mark.asyncio
async def test_class_boxplot(client, school_admin_headers, seed_school, db):
    _, exam2, cls, _ = await _seed_two_exams(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam2.id}/class-boxplot",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["classes"]) >= 1
    c = data["classes"][0]
    assert "min" in c and "max" in c and "median" in c and "p25" in c and "p75" in c
    assert c["min"] <= c["median"] <= c["max"]
