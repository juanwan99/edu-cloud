"""Tests for exam_import.service — student matching + commit write chain."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Student, Class
from edu_cloud.modules.exam.models import Exam, Subject, Question, ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.exam_import.parser import (
    ParsedExamData,
    ParsedSubjectData,
    StudentScore,
    QuestionDef,
)
from edu_cloud.modules.exam_import.service import (
    match_students,
    commit_import,
    run_post_import_pipeline,
    _normalize_class,
    MatchResult,
)
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.bank.models import StudentErrorBook

pytestmark = pytest.mark.asyncio


# ── helpers ──────────────────────────────────────────────────────


async def _seed_school(db: AsyncSession) -> School:
    school = School(name="导入测试校", code="IMP01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    return school


async def _seed_class(db: AsyncSession, school_id: str, name: str, grade: str = "高一") -> Class:
    cls = Class(name=name, grade=grade, school_id=school_id)
    db.add(cls)
    await db.flush()
    return cls


async def _seed_student(
    db: AsyncSession,
    school_id: str,
    name: str,
    number: str,
    class_id: str | None = None,
) -> Student:
    stu = Student(
        name=name,
        student_number=number,
        school_id=school_id,
        class_id=class_id,
    )
    db.add(stu)
    await db.flush()
    return stu


# ── normalize_class tests ────────────────────────────────────────


def test_normalize_class_plain():
    assert _normalize_class("2301班") == "2301"


def test_normalize_class_prefix():
    assert _normalize_class("高一年级2301班") == "2301"


def test_normalize_class_bare():
    assert _normalize_class("2301") == "2301"


def test_normalize_class_empty():
    assert _normalize_class(None) == ""
    assert _normalize_class("") == ""


# ── match_students tests ────────────────────────────────────────


async def test_match_students_by_number(db: AsyncSession):
    """Exact match on student_number == student_key."""
    school = await _seed_school(db)
    cls = await _seed_class(db, school.id, "2301班")
    stu = await _seed_student(db, school.id, "张三", "2301001", cls.id)
    await db.commit()

    parsed = [
        StudentScore(
            student_key="2301001",
            student_name="张三",
            class_name="2301班",
        ),
    ]

    result = await match_students(db, parsed, school.id)

    assert len(result.matched) == 1
    assert result.matched[0].edu_student_id == stu.id
    assert result.matched[0].edu_class_id == cls.id
    assert result.matched[0].match_method == "number"
    assert len(result.unmatched) == 0
    assert len(result.ambiguous) == 0


async def test_match_students_fallback_name_class(db: AsyncSession):
    """Fallback match on (name, normalized_class_name) when number misses."""
    school = await _seed_school(db)
    cls = await _seed_class(db, school.id, "高一年级2302班")
    stu = await _seed_student(db, school.id, "李四", "X999", cls.id)
    await db.commit()

    parsed = [
        StudentScore(
            student_key="WRONG_KEY",
            student_name="李四",
            class_name="2302班",
        ),
    ]

    result = await match_students(db, parsed, school.id)

    assert len(result.matched) == 1
    assert result.matched[0].edu_student_id == stu.id
    assert result.matched[0].match_method == "name_class"


async def test_match_students_unmatched(db: AsyncSession):
    """Student not in DB at all → unmatched."""
    school = await _seed_school(db)
    await db.commit()

    parsed = [
        StudentScore(
            student_key="NONEXIST",
            student_name="王五",
            class_name="9999班",
        ),
    ]

    result = await match_students(db, parsed, school.id)

    assert len(result.matched) == 0
    assert len(result.unmatched) == 1
    assert result.unmatched[0].student_name == "王五"


async def test_match_students_ambiguous(db: AsyncSession):
    """Two students with same name in same class → ambiguous."""
    school = await _seed_school(db)
    cls = await _seed_class(db, school.id, "2303班")
    stu1 = await _seed_student(db, school.id, "赵六", "A001", cls.id)
    stu2 = await _seed_student(db, school.id, "赵六", "A002", cls.id)
    await db.commit()

    parsed = [
        StudentScore(
            student_key="WRONG",
            student_name="赵六",
            class_name="2303班",
        ),
    ]

    result = await match_students(db, parsed, school.id)

    assert len(result.ambiguous) == 1
    parsed_item, candidate_ids = result.ambiguous[0]
    assert parsed_item.student_name == "赵六"
    assert set(candidate_ids) == {stu1.id, stu2.id}


# ── commit_import tests ─────────────────────────────────────────


def _make_parsed_data(
    subject_name: str = "语文",
    subject_code: str = "YW",
    questions: list[QuestionDef] | None = None,
    students: list[StudentScore] | None = None,
) -> ParsedExamData:
    """Helper to build a ParsedExamData for tests."""
    if questions is None:
        questions = [
            QuestionDef(name="选择1", question_type="choice", max_score=3.0, correct_answer="A"),
            QuestionDef(name="选择2", question_type="choice", max_score=3.0, correct_answer="B"),
            QuestionDef(name="17", question_type="essay", max_score=10.0),
        ]
    if students is None:
        students = [
            StudentScore(
                student_key="S001",
                student_name="甲",
                raw_total=85.0,
                class_rank=1,
                school_rank=5,
                question_scores={"选择1": 3.0, "选择2": 0.0, "17": 8.0},
            ),
        ]
    return ParsedExamData(
        subjects=[
            ParsedSubjectData(
                subject_name=subject_name,
                subject_code=subject_code,
                questions=questions,
                students=students,
            ),
        ],
    )


async def _seed_for_commit(db: AsyncSession):
    """Seed school + class + student for commit tests, return (school, student)."""
    school = await _seed_school(db)
    cls = await _seed_class(db, school.id, "2301班")
    stu = await _seed_student(db, school.id, "甲", "S001", cls.id)
    await db.commit()

    from edu_cloud.modules.exam_import.service import MatchedStudent

    matched = {
        "S001": MatchedStudent(
            parsed=StudentScore(student_key="S001", student_name="甲"),
            edu_student_id=stu.id,
            edu_class_id=cls.id,
            match_method="number",
        ),
    }
    return school, stu, matched


async def test_commit_import_creates_full_chain(db: AsyncSession):
    """Full chain: Exam→Subject→Question→StudentAnswer→GradingResult→ExamResult."""
    school, stu, matched = await _seed_for_commit(db)
    parsed = _make_parsed_data()

    stats = await commit_import(
        db,
        parsed=parsed,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
    )

    # Verify Exam
    exam = (await db.execute(select(Exam).where(Exam.id == stats["exam_id"]))).scalar_one()
    assert exam.name == "联考期中"
    assert exam.source == "import_questions"
    assert exam.status == "completed"

    # Verify Subject
    subjects = (await db.execute(select(Subject).where(Subject.exam_id == exam.id))).scalars().all()
    assert len(subjects) == 1
    assert subjects[0].code == "YW"

    # Verify Questions
    questions = (await db.execute(
        select(Question).where(Question.subject_id == subjects[0].id)
    )).scalars().all()
    assert len(questions) == 3
    q_names = {q.name for q in questions}
    assert q_names == {"选择1", "选择2", "17"}

    # Verify StudentAnswers
    answers = (await db.execute(
        select(StudentAnswer).where(StudentAnswer.exam_id == exam.id)
    )).scalars().all()
    assert len(answers) == 3  # 3 questions x 1 student

    # Check choice full-score → detected_answer
    choice1_answer = next(a for a in answers if a.score == 3.0 and a.detected_answer == "A")
    assert choice1_answer is not None

    # Verify GradingResults
    gr_count = len((await db.execute(
        select(GradingResult).where(GradingResult.school_id == school.id)
    )).scalars().all())
    assert gr_count == 3

    # Check GradingResult source and status
    gr_sample = (await db.execute(
        select(GradingResult).where(GradingResult.answer_id == answers[0].id)
    )).scalar_one()
    assert gr_sample.status == "confirmed"
    assert gr_sample.source == "import_questions"

    # Verify ExamResult
    er = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam.id,
            ExamResult.student_id == stu.id,
        )
    )).scalar_one()
    assert er.total_score == 85.0
    assert er.rank_in_class == 1
    assert er.rank_in_grade == 5

    # Stats sanity
    assert stats["subjects_created"] == 1
    assert stats["questions_created"] == 3
    assert stats["answers_created"] == 3
    assert stats["grading_results_created"] == 3
    assert stats["exam_results_created"] == 1


async def test_commit_import_upsert_idempotent(db: AsyncSession):
    """Re-importing with same exam updates scores rather than creating duplicates."""
    school, stu, matched = await _seed_for_commit(db)
    parsed = _make_parsed_data()

    # First import
    stats1 = await commit_import(
        db,
        parsed=parsed,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
    )
    exam_id = stats1["exam_id"]

    # Modify score and re-import with existing exam
    parsed2 = _make_parsed_data(
        students=[
            StudentScore(
                student_key="S001",
                student_name="甲",
                raw_total=90.0,
                class_rank=1,
                school_rank=3,
                question_scores={"选择1": 3.0, "选择2": 3.0, "17": 9.0},
            ),
        ],
    )

    stats2 = await commit_import(
        db,
        parsed=parsed2,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
        existing_exam_id=exam_id,
    )

    # Should update, not create new
    assert stats2["questions_updated"] == 3
    assert stats2["questions_created"] == 0
    assert stats2["answers_updated"] == 3
    assert stats2["answers_created"] == 0
    assert stats2["exam_results_updated"] == 1
    assert stats2["exam_results_created"] == 0

    # Verify updated score
    er = (await db.execute(
        select(ExamResult).where(
            ExamResult.exam_id == exam_id,
            ExamResult.student_id == stu.id,
        )
    )).scalar_one()
    assert er.total_score == 90.0
    assert er.rank_in_grade == 3

    # Verify updated answer score (选择2 was 0 → now 3.0 with detected_answer)
    q2 = (await db.execute(
        select(Question).where(Question.name == "选择2")
    )).scalar_one()
    ans2 = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.question_id == q2.id,
            StudentAnswer.student_id == stu.id,
        )
    )).scalar_one()
    assert ans2.score == 3.0
    assert ans2.detected_answer == "B"  # full score → correct_answer


async def test_commit_absent_then_normal(db: AsyncSession):
    """Absent → normal import: is_absent clears, GradingResult gets score."""
    school, stu, matched = await _seed_for_commit(db)

    # Step 1: import as absent
    absent_student = StudentScore(
        student_key="S001",
        student_name="甲",
        raw_total=None,
        is_absent=True,
        question_scores={},
    )
    parsed_absent = _make_parsed_data(students=[absent_student])

    stats1 = await commit_import(
        db,
        parsed=parsed_absent,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
    )
    exam_id = stats1["exam_id"]
    assert stats1["absent_marked"] > 0

    # Verify absent state
    answers = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.student_id == stu.id,
        )
    )).scalars().all()
    assert all(a.is_absent is True for a in answers)
    assert all(a.score is None for a in answers)

    # Step 2: re-import as normal (student actually took the exam)
    normal_student = StudentScore(
        student_key="S001",
        student_name="甲",
        raw_total=85.0,
        class_rank=1,
        school_rank=5,
        is_absent=False,
        question_scores={"选择1": 3.0, "选择2": 0.0, "17": 8.0},
    )
    parsed_normal = _make_parsed_data(students=[normal_student])

    stats2 = await commit_import(
        db,
        parsed=parsed_normal,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
        existing_exam_id=exam_id,
    )

    # Verify answers flipped to normal
    answers = (await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.exam_id == exam_id,
            StudentAnswer.student_id == stu.id,
        )
    )).scalars().all()
    assert all(a.is_absent is False for a in answers)

    # At least one answer has a score
    scored = [a for a in answers if a.score is not None]
    assert len(scored) >= 2  # 选择1=3.0, 17=8.0

    # GradingResult should now have final_score
    gr_list = (await db.execute(
        select(GradingResult).where(GradingResult.school_id == school.id)
    )).scalars().all()
    scored_gr = [g for g in gr_list if g.final_score is not None]
    assert len(scored_gr) >= 2
    assert all(g.status == "confirmed" for g in gr_list)
    assert all(g.source == "import_questions" for g in scored_gr)


# ── run_post_import_pipeline tests ──────────────────────────────


async def test_post_import_pipeline_preserves_converted_score(db: AsyncSession):
    """Pipeline generates snapshot and preserves imported converted_score."""
    school, stu, matched = await _seed_for_commit(db)

    # Build parsed data with converted_score and raw_total
    parsed = _make_parsed_data(
        students=[
            StudentScore(
                student_key="S001",
                student_name="甲",
                raw_total=85.0,
                converted_score=85.0,
                class_rank=1,
                school_rank=5,
                question_scores={"选择1": 3.0, "选择2": 0.0, "17": 8.0},
            ),
        ],
    )

    # Step 1: commit the import
    stats = await commit_import(
        db,
        parsed=parsed,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="questions",
    )
    exam_id = stats["exam_id"]

    # Step 2: run pipeline
    pipeline_result = await run_post_import_pipeline(
        db,
        exam_id=exam_id,
        school_id=school.id,
        import_mode="questions",
        parsed=parsed,
        matched_students=matched,
    )

    assert pipeline_result["snapshots"] >= 1
    assert pipeline_result["overrides"] >= 1

    # Verify snapshot has converted_score preserved
    snap = (await db.execute(select(StudentExamSnapshot).where(
        StudentExamSnapshot.student_id == stu.id,
        StudentExamSnapshot.exam_id == exam_id,
        StudentExamSnapshot.subject_code == "YW",
    ))).scalar_one()

    assert snap.converted_score == 85.0
    assert snap.total_score == 85.0
    assert snap.class_rank == 1
    assert snap.grade_rank == 5


async def test_post_import_pipeline_totals_skips_error_books(db: AsyncSession):
    """Totals mode skips error_book generation."""
    school, stu, matched = await _seed_for_commit(db)

    parsed = _make_parsed_data(
        students=[
            StudentScore(
                student_key="S001",
                student_name="甲",
                raw_total=85.0,
                class_rank=1,
                school_rank=5,
                question_scores={"选择1": 3.0, "选择2": 0.0, "17": 8.0},
            ),
        ],
    )

    # Commit with totals mode
    stats = await commit_import(
        db,
        parsed=parsed,
        matched_students=matched,
        school_id=school.id,
        exam_name="联考期中",
        exam_type="joint",
        grade_scope="高一",
        import_mode="totals",
    )
    exam_id = stats["exam_id"]

    # Run pipeline with totals mode
    pipeline_result = await run_post_import_pipeline(
        db,
        exam_id=exam_id,
        school_id=school.id,
        import_mode="totals",
        parsed=parsed,
        matched_students=matched,
    )

    # Snapshots should be generated
    assert pipeline_result["snapshots"] >= 1
    # Error books should be skipped
    assert pipeline_result["error_books"] == 0
    assert pipeline_result["error_patterns"] == 0

    # Double-check no error book entries exist
    error_books = (await db.execute(select(StudentErrorBook).where(
        StudentErrorBook.exam_id == exam_id,
    ))).scalars().all()
    assert len(error_books) == 0
