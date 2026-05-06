import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.student import Class, Student
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult, GradingPipelineLog


async def _seed_ai_report_exam(db):
    school = School(name="AI Report School", code="AIRPT")
    db.add(school)
    await db.flush()

    cls = Class(name="2501班", grade="七年级", school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for idx in range(2):
        student = Student(
            name=f"学生{idx+1}",
            student_number=f"372223010{idx+1}",
            class_id=cls.id,
            school_id=school.id,
        )
        db.add(student)
        students.append(student)
    await db.flush()

    exam = Exam(name="AI 期中", card_title="AI 期中", school_id=school.id, status="completed")
    db.add(exam)
    await db.flush()

    subject = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    db.add(subject)
    await db.flush()

    q_choice = Question(subject_id=subject.id, school_id=school.id, name="1", question_type="choice", max_score=3)
    q_essay = Question(subject_id=subject.id, school_id=school.id, name="12", question_type="essay", max_score=10)
    db.add_all([q_choice, q_essay])
    await db.flush()

    # Student 1: UUID choice + barcode essay, AI was changed by final score.
    choice1 = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id=students[0].id,
        question_id=q_choice.id, school_id=school.id, score=3.0,
        detected_answer="A", question_type="choice",
    )
    essay1 = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id="250101",
        question_id=q_essay.id, school_id=school.id, question_type="essay",
    )
    # Student 2: barcode essay, low confidence.
    essay2 = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id="250102",
        question_id=q_essay.id, school_id=school.id, question_type="essay",
    )
    db.add_all([choice1, essay1, essay2])
    await db.flush()

    db.add_all([
        GradingResult(
            answer_id=essay1.id, question_id=q_essay.id, school_id=school.id,
            ai_score=7.0, ai_confidence=0.92, final_score=8.0, max_score=10.0,
            status="confirmed", source="ai_override",
            ai_raw_response={"details": [{"blanks": [{"correct": False, "reason": "概念混淆"}]}]},
        ),
        GradingResult(
            answer_id=essay2.id, question_id=q_essay.id, school_id=school.id,
            ai_score=4.0, ai_confidence=0.35, final_score=None, max_score=10.0,
            status="ai_done", source=None,
            ai_raw_response={"details": [{"blanks": [{"correct": False, "reason": "步骤不完整"}]}]},
        ),
    ])
    db.add_all([
        GradingPipelineLog(
            answer_id=essay1.id, question_id=q_essay.id, school_id=school.id,
            subject_code="YW", question_type="essay", pipeline_type="two_step",
            is_blank=False, total_ms=1000, confidence=0.91, score=7.0,
        ),
        GradingPipelineLog(
            answer_id=essay2.id, question_id=q_essay.id, school_id=school.id,
            subject_code="YW", question_type="essay", pipeline_type="two_step",
            is_blank=True, total_ms=2000, confidence=0.35, score=4.0,
            error_type="low_confidence",
        ),
    ])
    await db.commit()
    return school, cls, students, exam, subject


@pytest.mark.asyncio
async def test_ai_grading_report_exposes_ai_specific_quality_metrics(db):
    school, cls, students, exam, subject = await _seed_ai_report_exam(db)

    from edu_cloud.modules.analytics.ai_report_service import build_ai_grading_report

    report = await build_ai_grading_report(db, exam_id=exam.id, school_id=school.id)

    assert report["exam_id"] == exam.id
    assert report["coverage"]["answer_count"] == 3
    assert report["coverage"]["ai_scored_count"] == 2
    assert report["coverage"]["confirmed_count"] == 1
    assert report["coverage"]["pending_review_count"] == 1
    assert report["confidence"]["low_confidence_count"] == 1
    assert report["quality"]["ai_human_delta_count"] == 1
    assert report["quality"]["avg_abs_delta"] == 1.0
    assert report["quality"]["override_count"] == 1
    assert report["ocr_pipeline"]["blank_count"] == 1
    assert report["ocr_pipeline"]["error_count"] == 1
    assert report["question_diagnostics"][0]["error_causes"][0]["cause"] in {"概念混淆", "步骤不完整"}
    assert report["student_watchlist"][0]["student_id"] in {students[0].id, students[1].id}
    assert report["teaching_actions"]


@pytest.mark.asyncio
async def test_ai_grading_report_respects_canonical_class_filter(db):
    school, cls, students, exam, subject = await _seed_ai_report_exam(db)

    from edu_cloud.modules.analytics.ai_report_service import build_ai_grading_report

    report = await build_ai_grading_report(
        db, exam_id=exam.id, school_id=school.id, class_id=cls.id,
    )

    assert report["coverage"]["answer_count"] == 3
    assert report["coverage"]["matched_student_count"] == 2


@pytest.mark.asyncio
async def test_ai_grading_report_excludes_absent_answers(db):
    school, cls, students, exam, subject = await _seed_ai_report_exam(db)

    qid = (
        await db.execute(
            select(Question.id).where(
                Question.subject_id == subject.id,
                Question.question_type == "essay",
            )
        )
    ).scalar_one()
    absent = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id=students[0].id,
        question_id=qid, school_id=school.id, question_type="essay",
        is_absent=True,
    )
    db.add(absent)
    await db.flush()
    db.add(GradingResult(
        answer_id=absent.id, question_id=qid, school_id=school.id,
        ai_score=10.0, ai_confidence=0.99, final_score=10.0,
        max_score=10.0, status="confirmed", source="ai",
    ))
    await db.commit()

    from edu_cloud.modules.analytics.ai_report_service import build_ai_grading_report

    report = await build_ai_grading_report(db, exam_id=exam.id, school_id=school.id)

    assert report["coverage"]["answer_count"] == 3
    assert report["coverage"]["ai_scored_count"] == 2


def test_ai_report_chunks_large_answer_id_queries():
    from edu_cloud.modules.analytics.ai_report_service import SQL_IN_CHUNK_SIZE, _chunks

    answer_ids = [f"a{i}" for i in range(SQL_IN_CHUNK_SIZE * 2 + 1)]
    batches = list(_chunks(answer_ids))

    assert [len(batch) for batch in batches] == [
        SQL_IN_CHUNK_SIZE,
        SQL_IN_CHUNK_SIZE,
        1,
    ]
    assert batches[0][0] == "a0"
    assert batches[-1][-1] == f"a{SQL_IN_CHUNK_SIZE * 2}"
