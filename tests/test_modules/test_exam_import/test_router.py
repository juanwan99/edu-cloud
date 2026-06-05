"""Tests for exam_import.router — ORM + parser integration smoke tests.

Two categories:
1. Direct ORM tests for ExamImportSession (no HTTP)
2. Parser→MatchResult integration (file-based)
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.core.tenant import TenantContext
from edu_cloud.modules.exam_import.models import ExamImportSession
from edu_cloud.modules.exam_import.parser import (
    ParsedExamData,
    ParsedSubjectData,
    StudentScore,
    QuestionDef,
)
from edu_cloud.modules.exam_import.router import _school_id_from
from edu_cloud.modules.exam_import.service import match_students
from edu_cloud.modules.student.models import Student, Class

pytestmark = pytest.mark.asyncio


async def test_school_scope_required_for_exam_import():
    tenant = TenantContext(
        user_id="u1",
        role_id="r1",
        role_name="platform_admin",
        school_id=None,
        visible_class_ids=None,
        visible_subject_codes=None,
    )

    with pytest.raises(HTTPException) as exc:
        _school_id_from(tenant)

    assert exc.value.status_code == 403


# ── helpers ──────────────────────────────────────────────────────


async def _seed_school(db: AsyncSession) -> School:
    school = School(name="路由测试校", code="RT01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    return school


# ── 1. ExamImportSession ORM tests ──────────────────────────────


async def test_create_import_session_model(db: AsyncSession):
    """ExamImportSession can be created and queried with all fields."""
    school = await _seed_school(db)

    session = ExamImportSession(
        school_id=school.id,
        exam_name="期中联考",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
        status="previewing",
        file_path="/tmp/test.xlsx",
        preview_data={
            "subjects": [{"name": "数学", "code": "SX"}],
            "match_summary": {"matched": 10, "unmatched": 2, "ambiguous": 0},
        },
    )
    db.add(session)
    await db.commit()

    # query back
    stmt = select(ExamImportSession).where(
        ExamImportSession.school_id == school.id,
    )
    result = (await db.execute(stmt)).scalar_one()
    assert result.exam_name == "期中联考"
    assert result.status == "previewing"
    assert result.import_mode == "questions"
    assert result.preview_data["match_summary"]["matched"] == 10
    assert result.file_path == "/tmp/test.xlsx"


async def test_import_session_school_isolation(db: AsyncSession):
    """Sessions for different schools are isolated."""
    school_a = School(name="学校A", code="SA01", district="测试区", api_key_hash="x")
    school_b = School(name="学校B", code="SB01", district="测试区", api_key_hash="x")
    db.add_all([school_a, school_b])
    await db.flush()

    for s in [school_a, school_b]:
        db.add(ExamImportSession(
            school_id=s.id,
            exam_name=f"{s.name}考试",
            exam_type="midterm",
            grade_scope="高一",
            import_mode="totals",
            status="previewing",
        ))
    await db.commit()

    # query school_a only
    stmt = select(ExamImportSession).where(
        ExamImportSession.school_id == school_a.id,
    )
    rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 1
    assert rows[0].exam_name == "学校A考试"


async def test_import_session_status_transitions(db: AsyncSession):
    """Session status can transition through the lifecycle."""
    school = await _seed_school(db)

    session = ExamImportSession(
        school_id=school.id,
        exam_name="状态测试",
        exam_type="final",
        grade_scope="高二",
        import_mode="questions",
        status="previewing",
    )
    db.add(session)
    await db.commit()

    # transition to committed
    session.status = "committed"
    session.result_summary = {"exam_id": "test-exam-id", "subjects_created": 3}
    await db.commit()

    await db.refresh(session)
    assert session.status == "committed"
    assert session.result_summary["subjects_created"] == 3

    # separate session for cancelled flow
    session2 = ExamImportSession(
        school_id=school.id,
        exam_name="取消测试",
        exam_type="quiz",
        grade_scope="高三",
        import_mode="totals",
        status="previewing",
    )
    db.add(session2)
    await db.commit()

    session2.status = "cancelled"
    await db.commit()

    await db.refresh(session2)
    assert session2.status == "cancelled"


# ── 2. Parser → MatchResult integration ─────────────────────────


async def test_parser_integration_from_parsed_data(db: AsyncSession):
    """ParsedExamData → match_students works with in-memory data."""
    school = await _seed_school(db)

    cls = Class(name="2301班", grade="高一", school_id=school.id)
    db.add(cls)
    await db.flush()

    # seed two students
    stu1 = Student(name="张三", student_number="S001", school_id=school.id, class_id=cls.id, grade="高一")
    stu2 = Student(name="李四", student_number="S002", school_id=school.id, class_id=cls.id, grade="高一")
    db.add_all([stu1, stu2])
    await db.commit()

    # build parsed students
    parsed_students = [
        StudentScore(student_key="S001", student_name="张三", class_name="2301班", raw_total=130.0),
        StudentScore(student_key="S002", student_name="李四", class_name="2301班", raw_total=125.0),
        StudentScore(student_key="S999", student_name="王五", class_name="2301班", raw_total=110.0),
    ]

    result = await match_students(db, parsed_students, school.id)

    assert len(result.matched) == 2
    assert len(result.unmatched) == 1
    assert result.unmatched[0].student_name == "王五"

    # verify matched student IDs
    matched_keys = {m.parsed.student_key for m in result.matched}
    assert matched_keys == {"S001", "S002"}

    # verify match method
    for m in result.matched:
        assert m.match_method == "number"


async def test_parser_match_by_name_class_fallback(db: AsyncSession):
    """Students without student_number can match by name+class."""
    school = await _seed_school(db)

    cls = Class(name="高一年级2301班", grade="高一", school_id=school.id)
    db.add(cls)
    await db.flush()

    stu = Student(name="赵六", student_number="", school_id=school.id, class_id=cls.id, grade="高一")
    db.add(stu)
    await db.commit()

    # parsed student has no student_key but has name+class
    parsed_students = [
        StudentScore(student_key="", student_name="赵六", class_name="高一年级2301班"),
    ]

    result = await match_students(db, parsed_students, school.id)
    assert len(result.matched) == 1
    assert result.matched[0].match_method == "name_class"


async def test_parsed_exam_data_to_match_result_full_chain(db: AsyncSession):
    """Full chain: construct ParsedExamData with subjects → flatten students → match."""
    school = await _seed_school(db)

    cls = Class(name="2302班", grade="高一", school_id=school.id)
    db.add(cls)
    await db.flush()

    stu = Student(name="孙七", student_number="S007", school_id=school.id, class_id=cls.id, grade="高一")
    db.add(stu)
    await db.commit()

    # construct full ParsedExamData
    parsed = ParsedExamData(
        subjects=[
            ParsedSubjectData(
                subject_name="数学",
                subject_code="SX",
                questions=[
                    QuestionDef(name="选择1", question_type="choice", max_score=5.0),
                    QuestionDef(name="17", question_type="essay", max_score=12.0),
                ],
                students=[
                    StudentScore(
                        student_key="S007",
                        student_name="孙七",
                        class_name="2302班",
                        raw_total=135.0,
                        question_scores={"选择1": 5.0, "17": 10.0},
                    ),
                    StudentScore(
                        student_key="SXXX",
                        student_name="不存在",
                        class_name="9999班",
                        raw_total=100.0,
                    ),
                ],
            ),
        ],
        warnings=[],
    )

    # flatten all students across subjects (same as router does)
    all_students = []
    for subj in parsed.subjects:
        all_students.extend(subj.students)

    result = await match_students(db, all_students, school.id)

    assert len(result.matched) == 1
    assert result.matched[0].parsed.student_key == "S007"
    assert result.matched[0].parsed.raw_total == 135.0
    assert len(result.unmatched) == 1
    assert result.unmatched[0].student_key == "SXXX"
