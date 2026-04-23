import pytest
from datetime import datetime
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, ExamResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.shared.auth import create_access_token
from tests.conftest import *  # noqa — reuse fixtures


@pytest.fixture
async def school_admin_headers(db, seed_school):
    """principal role bound to test school for school-scoped endpoint tests."""
    school, _ = seed_school
    user = User(username="school_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="principal",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_power_options_empty(client, school_admin_headers):
    """No completed exams → empty grades list."""
    resp = await client.get(
        "/api/v1/analytics/power-options",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"grades": []}


async def _seed_exam_data(db, seed_school):
    """Seed: 2 grades x 2+1 classes x 2 subjects x 2 exams."""
    school, _ = seed_school
    school_id = school.id
    cls_g1_1 = Class(name="高一(1)班", grade="高一", school_id=school_id)
    cls_g1_2 = Class(name="高一(2)班", grade="高一", school_id=school_id)
    cls_g2_1 = Class(name="高二(1)班", grade="高二", school_id=school_id)
    db.add_all([cls_g1_1, cls_g1_2, cls_g2_1])
    await db.flush()

    exam1 = Exam(name="期中考试", status="completed", school_id=school_id,
                 exam_date=datetime(2026, 4, 10))
    exam2 = Exam(name="月考", status="completed", school_id=school_id,
                 exam_date=datetime(2026, 3, 5))
    exam_draft = Exam(name="未完成", status="draft", school_id=school_id)
    db.add_all([exam1, exam2, exam_draft])
    await db.flush()

    subj_math = Subject(exam_id=exam1.id, name="数学", code="math", school_id=school_id)
    subj_chinese = Subject(exam_id=exam1.id, name="语文", code="chinese", school_id=school_id)
    subj_math2 = Subject(exam_id=exam2.id, name="数学", code="math", school_id=school_id)
    db.add_all([subj_math, subj_chinese, subj_math2])
    await db.flush()

    stu1 = Student(name="张三", student_number="S001", class_id=cls_g1_1.id,
                   grade="高一", school_id=school_id)
    stu2 = Student(name="李四", student_number="S002", class_id=cls_g1_2.id,
                   grade="高一", school_id=school_id)
    stu3 = Student(name="王五", student_number="S003", class_id=cls_g2_1.id,
                   grade="高二", school_id=school_id)
    db.add_all([stu1, stu2, stu3])
    await db.flush()

    db.add_all([
        ExamResult(exam_id=exam1.id, student_id=stu1.id, school_id=school_id, total_score=85),
        ExamResult(exam_id=exam1.id, student_id=stu2.id, school_id=school_id, total_score=72),
        ExamResult(exam_id=exam2.id, student_id=stu1.id, school_id=school_id, total_score=90),
        ExamResult(exam_id=exam1.id, student_id=stu3.id, school_id=school_id, total_score=60),
    ])
    await db.commit()
    return {
        "exam1": exam1, "exam2": exam2,
        "cls_g1_1": cls_g1_1, "cls_g1_2": cls_g1_2, "cls_g2_1": cls_g2_1,
        "subj_math": subj_math, "subj_chinese": subj_chinese,
    }


@pytest.mark.asyncio
async def test_power_options_tree_structure(client, school_admin_headers, seed_school, db):
    """Multi-grade multi-class multi-subject: verify tree + all node."""
    await _seed_exam_data(db, seed_school)

    resp = await client.get("/api/v1/analytics/power-options", headers=school_admin_headers)
    assert resp.status_code == 200
    result = resp.json()

    grades = result["grades"]
    grade_names = [g["name"] for g in grades]
    assert "高一" in grade_names
    assert "高二" in grade_names

    g1 = next(g for g in grades if g["name"] == "高一")
    assert g1["id"] == "高一", "ORC-001: grade node must have unified id"
    class_ids = [c["id"] for c in g1["classes"]]
    assert "all" in class_ids

    all_node = next(c for c in g1["classes"] if c["id"] == "all")
    assert len(all_node["subjects"]) >= 1

    # ORC-002: all student_count == sum of real classes
    for subj in all_node["subjects"]:
        for exam in subj["exams"]:
            total = 0
            for cls in g1["classes"]:
                if cls["id"] == "all":
                    continue
                for s in cls["subjects"]:
                    if s["id"] == subj["id"]:
                        for e in s["exams"]:
                            if e["exam_id"] == exam["exam_id"]:
                                total += e["student_count"]
            assert exam["student_count"] == total, (
                f"ORC-002: all.student_count({exam['student_count']}) != sum({total})"
            )


@pytest.mark.asyncio
async def test_power_options_excludes_draft(client, school_admin_headers, seed_school, db):
    """Draft exams must not appear in power-options tree."""
    await _seed_exam_data(db, seed_school)

    resp = await client.get("/api/v1/analytics/power-options", headers=school_admin_headers)
    result = resp.json()
    all_exam_names = []
    for g in result["grades"]:
        for c in g["classes"]:
            for s in c["subjects"]:
                for e in s["exams"]:
                    all_exam_names.append(e["name"])
    assert "未完成" not in all_exam_names


@pytest.mark.asyncio
async def test_power_options_rbac_subject_filter(client, db, seed_school):
    """Subject teacher only sees their own subjects."""
    await _seed_exam_data(db, seed_school)

    school, _ = seed_school
    teacher = User(username="math_teacher", display_name="数学老师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(
        user_id=teacher.id, role="subject_teacher",
        school_id=school.id, is_primary=True,
        subject_codes=["math"],
    ))
    await db.commit()
    token = create_access_token({"sub": teacher.id, "role": "subject_teacher"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/analytics/power-options", headers=headers)
    assert resp.status_code == 200
    result = resp.json()

    for g in result["grades"]:
        for c in g["classes"]:
            for s in c["subjects"]:
                assert s["code"] == "math", f"ORC-004: subject teacher sees non-math subject {s['code']}"
