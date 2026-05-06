import pytest

from edu_cloud.models.school import School
from edu_cloud.models.student import Class, Student
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from sqlalchemy import select


async def _seed_barcode_exam(db):
    school = School(name="Identity School", code="IDMAP")
    db.add(school)
    await db.flush()

    cls = Class(name="2501班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()

    student = Student(
        name="学生甲",
        student_number="3722230101",
        class_id=cls.id,
        school_id=school.id,
    )
    db.add(student)
    await db.flush()

    exam = Exam(name="期中考试", card_title="期中", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subject = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    db.add(subject)
    await db.flush()

    q_choice = Question(
        subject_id=subject.id, school_id=school.id,
        name="1", question_type="choice", max_score=3.0,
    )
    q_essay = Question(
        subject_id=subject.id, school_id=school.id,
        name="12", question_type="essay", max_score=10.0,
    )
    db.add_all([q_choice, q_essay])
    await db.flush()

    choice = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id=student.id,
        question_id=q_choice.id, school_id=school.id, score=3.0,
    )
    essay = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id="250101",
        question_id=q_essay.id, school_id=school.id, score=None,
    )
    db.add_all([choice, essay])
    await db.flush()

    db.add(GradingResult(
        answer_id=essay.id, question_id=q_essay.id, school_id=school.id,
        ai_score=8.0, final_score=9.0, max_score=10.0, status="confirmed", source="manual",
    ))
    await db.commit()
    return school, cls, student, exam, subject


@pytest.mark.asyncio
async def test_resolve_student_identity_matches_uuid_and_jingyan_barcode(db):
    school, cls, student, *_ = await _seed_barcode_exam(db)

    from edu_cloud.modules.analytics.identity import resolve_student_identities

    resolved = await resolve_student_identities(
        db, school_id=school.id, raw_student_ids=[student.id, "250101", "251756"]
    )

    assert resolved[student.id].canonical_student_id == student.id
    assert resolved[student.id].match_method == "student_id"
    assert resolved["250101"].canonical_student_id == student.id
    assert resolved["250101"].class_id == cls.id
    assert resolved["250101"].match_method == "jingyan_25_last4"
    assert resolved["251756"].canonical_student_id is None
    assert resolved["251756"].match_status == "unmatched"


@pytest.mark.asyncio
async def test_get_effective_scores_merges_uuid_choice_and_barcode_essay(db):
    school, cls, student, exam, subject = await _seed_barcode_exam(db)

    from edu_cloud.modules.analytics import get_effective_scores

    rows = await get_effective_scores(db, subject.id, school.id)

    assert len(rows) == 2
    assert {r["student_id"] for r in rows} == {student.id}
    assert {r["raw_student_id"] for r in rows} == {student.id, "250101"}
    assert {r["class_id"] for r in rows} == {cls.id}
    assert sum(r["effective_score"] for r in rows) == 12.0

    class_rows = await get_effective_scores(db, subject.id, school.id, visible_class_ids=[cls.id])
    assert len(class_rows) == 2


@pytest.mark.asyncio
async def test_get_effective_scores_excludes_unmatched_barcode_when_roster_matches_exist(db):
    school, _cls, student, _exam, subject = await _seed_barcode_exam(db)
    question_id = (
        await db.execute(
            select(StudentAnswer.question_id).where(StudentAnswer.student_id == student.id)
        )
    ).scalar_one()
    unmatched = StudentAnswer(
        exam_id=_exam.id, subject_id=subject.id, student_id="251756",
        question_id=question_id, school_id=school.id, score=3.0,
    )
    db.add(unmatched)
    await db.commit()

    from edu_cloud.modules.analytics import get_effective_scores

    rows = await get_effective_scores(db, subject.id, school.id)

    assert "251756" not in {row["student_id"] for row in rows}
    assert {row["student_id"] for row in rows} == {student.id}


@pytest.mark.asyncio
async def test_generate_exam_snapshots_uses_canonical_student_identity(db):
    school, cls, student, exam, subject = await _seed_barcode_exam(db)

    from edu_cloud.modules.pipeline.service import generate_exam_snapshots
    from edu_cloud.modules.profile.models import StudentExamSnapshot

    created = await generate_exam_snapshots(db, exam_id=exam.id, school_id=school.id)

    assert created == 1
    result = await db.execute(
        select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == exam.id,
            StudentExamSnapshot.subject_code == subject.code,
        )
    )
    snaps = result.scalars().all()
    assert len(snaps) == 1
    assert snaps[0].student_id == student.id
    assert snaps[0].class_id_at_exam == cls.id
    assert snaps[0].total_score == 12.0
    assert snaps[0].class_rank == 1


@pytest.mark.asyncio
async def test_student_rankings_returns_canonical_student_display_fields(db):
    school, cls, student, exam, _subject = await _seed_barcode_exam(db)

    from edu_cloud.modules.analytics.ranking_service import student_rankings

    result = await student_rankings(db, exam_id=exam.id, school_id=school.id)

    assert result["students"] == [{
        "student_id": student.id,
        "name": "学生甲",
        "class_id": cls.id,
        "class_name": "2501班",
        "score": 12.0,
        "class_rank": 1,
        "grade_rank": 1,
        "prev_class_rank": None,
        "prev_grade_rank": None,
        "delta_class": None,
        "delta_grade": None,
    }]
