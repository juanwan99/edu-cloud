"""学生/成绩同步端点集成测试 — TDD."""
import pytest
from sqlalchemy import select, func

from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.models.exam import Exam, ExamResult


@pytest.mark.asyncio
async def test_sync_students(client, school_api_headers, db, seed_school):
    """TG-03: Verify sync creates ClassGroup and Students in DB."""
    school, _ = seed_school
    resp = await client.post("/api/v1/sync/students", json={
        "students": [
            {"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级", "gender": "男"},
            {"name": "李四", "student_number": "S002", "class_name": "七年级2班", "grade": "七年级", "gender": "女"},
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 2

    # TG-03: Verify ClassGroup was actually created in DB
    cls_result = await db.execute(
        select(ClassGroup).where(
            ClassGroup.name == "七年级2班",
            ClassGroup.school_id == school.id,
        )
    )
    cls = cls_result.scalar_one_or_none()
    assert cls is not None, "ClassGroup '七年级2班' should exist in DB after sync"
    assert cls.grade == "七年级"
    assert cls.school_id == school.id

    # TG-03: Verify Students were created with correct class_id
    s1_result = await db.execute(
        select(Student).where(
            Student.student_number == "S001",
            Student.school_id == school.id,
        )
    )
    s1 = s1_result.scalar_one()
    assert s1.name == "张三"
    assert s1.class_id == cls.id
    assert s1.gender == "男"

    s2_result = await db.execute(
        select(Student).where(
            Student.student_number == "S002",
            Student.school_id == school.id,
        )
    )
    s2 = s2_result.scalar_one()
    assert s2.name == "李四"
    assert s2.class_id == cls.id


@pytest.mark.asyncio
async def test_sync_students_upsert(client, school_api_headers, db, seed_school):
    """TG-03: 二次同步同一学号应更新而非新增重复记录。"""
    school, _ = seed_school
    payload = {"students": [{"name": "张三", "student_number": "S001", "grade": "七年级"}]}
    resp1 = await client.post("/api/v1/sync/students", json=payload, headers=school_api_headers)
    assert resp1.status_code == 200

    payload2 = {"students": [{"name": "张三新", "student_number": "S001", "grade": "七年级"}]}
    resp2 = await client.post("/api/v1/sync/students", json=payload2, headers=school_api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["synced_count"] == 1

    # TG-03: Verify upsert updated the existing record, not duplicated
    count_result = await db.execute(
        select(func.count()).select_from(Student).where(
            Student.student_number == "S001",
            Student.school_id == school.id,
        )
    )
    assert count_result.scalar() == 1, "Upsert should not duplicate student records"

    # TG-03: Verify the name was actually updated
    s_result = await db.execute(
        select(Student).where(
            Student.student_number == "S001",
            Student.school_id == school.id,
        )
    )
    student = s_result.scalar_one()
    assert student.name == "张三新", "Upsert should update student name"


@pytest.mark.asyncio
async def test_sync_exam_results(client, school_api_headers, db, seed_school):
    """TG-03: Verify exam and result records are created in DB."""
    school, _ = seed_school
    # First sync students
    await client.post("/api/v1/sync/students", json={
        "students": [{"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级"}]
    }, headers=school_api_headers)

    resp = await client.post("/api/v1/sync/exam-results", json={
        "exam": {"name": "期中考试", "subject_code": "SX", "subject_name": "数学", "max_score": 150, "semester": "2025-2026-2"},
        "results": [
            {"student_number": "S001", "total_score": 135.0}
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 1

    # TG-03: Verify Exam was created in DB
    exam_result = await db.execute(
        select(Exam).where(
            Exam.name == "期中考试",
            Exam.subject_code == "SX",
            Exam.school_id == school.id,
        )
    )
    exam = exam_result.scalar_one_or_none()
    assert exam is not None, "Exam should exist in DB after sync"
    assert exam.max_score == 150
    assert exam.semester == "2025-2026-2"

    # TG-03: Verify ExamResult links to the correct student
    student = (await db.execute(
        select(Student).where(
            Student.student_number == "S001",
            Student.school_id == school.id,
        )
    )).scalar_one()

    er_result = await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam.id,
            ExamResult.student_id == student.id,
        )
    )
    er = er_result.scalar_one_or_none()
    assert er is not None, "ExamResult should exist in DB after sync"
    assert er.total_score == 135.0


@pytest.mark.asyncio
async def test_sync_exam_results_unknown_student_skipped(client, school_api_headers):
    """未知学号的成绩应被跳过而非报错。"""
    resp = await client.post("/api/v1/sync/exam-results", json={
        "exam": {"name": "期末考试", "subject_code": "YW", "subject_name": "语文", "max_score": 150},
        "results": [
            {"student_number": "UNKNOWN_999", "total_score": 100.0}
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 0


@pytest.mark.asyncio
async def test_sync_exam_results_upsert(client, school_api_headers, db, seed_school):
    """TG-03: 同一考试同一学生二次上报应更新成绩，不重复。"""
    school, _ = seed_school
    await client.post("/api/v1/sync/students", json={
        "students": [{"name": "张三", "student_number": "S001", "grade": "七年级"}]
    }, headers=school_api_headers)

    exam_payload = {
        "exam": {"name": "期中考试", "subject_code": "SX"},
        "results": [{"student_number": "S001", "total_score": 120.0}],
    }
    resp1 = await client.post("/api/v1/sync/exam-results", json=exam_payload, headers=school_api_headers)
    assert resp1.status_code == 200

    exam_payload2 = {
        "exam": {"name": "期中考试", "subject_code": "SX"},
        "results": [{"student_number": "S001", "total_score": 135.0}],
    }
    resp2 = await client.post("/api/v1/sync/exam-results", json=exam_payload2, headers=school_api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["synced_count"] == 1

    # TG-03: Verify upsert updated the score, not duplicated
    student = (await db.execute(
        select(Student).where(
            Student.student_number == "S001",
            Student.school_id == school.id,
        )
    )).scalar_one()

    er_count = await db.execute(
        select(func.count()).select_from(ExamResult).where(
            ExamResult.student_id == student.id,
        )
    )
    assert er_count.scalar() == 1, "Upsert should not duplicate ExamResult records"

    # TG-03: Verify the score was updated to the new value
    er = (await db.execute(
        select(ExamResult).where(ExamResult.student_id == student.id)
    )).scalar_one()
    assert er.total_score == 135.0, "Upsert should update score to 135.0"


@pytest.mark.asyncio
async def test_sync_students_requires_auth(client):
    """无 API Key 应返回 422（缺少必填 header）。"""
    resp = await client.post("/api/v1/sync/students", json={"students": []})
    assert resp.status_code == 422
