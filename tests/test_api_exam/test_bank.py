import pytest
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.school import School


@pytest.mark.asyncio
async def test_create_bank_question(db):
    school = School(name="测试", code="BK01")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="choice", max_score=5, correct_answer="A")
    db.add(q)
    await db.flush()

    bq = BankQuestion(
        school_id=school.id, question_type="choice", max_score=5,
        correct_answer="A", source_exam_id=exam.id, source_question_id=q.id,
        difficulty=0.75, sample_count=100,
    )
    db.add(bq)
    await db.commit()
    assert bq.id is not None
    assert bq.difficulty == 0.75


@pytest.mark.asyncio
async def test_create_student_error_book(db):
    school = School(name="测试", code="BK02")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="3", question_type="essay", max_score=10)
    db.add(q)
    await db.flush()

    eb = StudentErrorBook(
        school_id=school.id, student_id="student-uuid-001", question_id=q.id,
        exam_id=exam.id, student_score=3.0, max_score=10.0,
        ai_feedback="概念混淆：将导数的几何意义理解为斜率的倒数",
        mastery_status="unmastered", source="auto",
    )
    db.add(eb)
    await db.commit()
    assert eb.id is not None
    assert eb.mastery_status == "unmastered"


@pytest.mark.asyncio
async def test_error_book_unique_per_student_question(db):
    school = School(name="测试", code="BK03")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q)
    await db.flush()

    db.add(StudentErrorBook(
        school_id=school.id, student_id="s001", question_id=q.id,
        exam_id=exam.id, student_score=2.0, max_score=10.0,
    ))
    await db.commit()

    from sqlalchemy.exc import IntegrityError
    db.add(StudentErrorBook(
        school_id=school.id, student_id="s001", question_id=q.id,
        exam_id=exam.id, student_score=3.0, max_score=10.0,
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
