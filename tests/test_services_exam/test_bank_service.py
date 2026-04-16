import pytest
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.modules.bank import service as bank_service
from edu_cloud.services.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_list_bank_questions_with_filter(db):
    school = School(name="测试", code="BS01")
    db.add(school)
    await db.flush()

    db.add(BankQuestion(school_id=school.id, question_type="choice", max_score=5, difficulty=0.8, sample_count=100))
    db.add(BankQuestion(school_id=school.id, question_type="essay", max_score=10, difficulty=0.4, sample_count=50))
    db.add(BankQuestion(school_id=school.id, question_type="choice", max_score=5, difficulty=0.3, sample_count=80))
    await db.commit()

    # 按类型
    result = await bank_service.list_bank_questions(db, school_id=school.id, question_type="choice")
    assert len(result) == 2

    # 按难度范围
    result = await bank_service.list_bank_questions(db, school_id=school.id, min_difficulty=0.5)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_error_book_stats(db):
    school = School(name="测试", code="BS02")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    for i, status in enumerate(["unmastered", "unmastered", "unmastered", "practicing", "mastered"]):
        q = Question(subject_id=subj.id, school_id=school.id, name=str(i+1), question_type="essay", max_score=10)
        db.add(q)
        await db.flush()
        db.add(StudentErrorBook(
            school_id=school.id, student_id="stu001", question_id=q.id,
            exam_id=exam.id, student_score=3.0, max_score=10.0,
            mastery_status=status,
        ))
    await db.commit()

    stats = await bank_service.get_error_book_stats(db, student_id="stu001", school_id=school.id)
    assert stats["total"] == 5
    assert stats["unmastered"] == 3
    assert stats["practicing"] == 1
    assert stats["mastered"] == 1


@pytest.mark.asyncio
async def test_get_bank_question_found(db):
    """TG-003: get_bank_question 命中。"""
    school = School(name="测试", code="BS03")
    db.add(school)
    await db.flush()
    bq = BankQuestion(school_id=school.id, question_type="choice", max_score=5, sample_count=10)
    db.add(bq)
    await db.commit()

    result = await bank_service.get_bank_question(db, bank_question_id=bq.id, school_id=school.id)
    assert result.id == bq.id


@pytest.mark.asyncio
async def test_get_bank_question_not_found(db):
    """TG-003: get_bank_question 不存在抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        await bank_service.get_bank_question(db, bank_question_id="nonexistent", school_id="any")


@pytest.mark.asyncio
async def test_get_student_error_book_with_filters(db):
    """TG-003: get_student_error_book mastery_status + limit 过滤。"""
    school = School(name="测试", code="BS04")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    for i, status in enumerate(["unmastered", "unmastered", "practicing"]):
        q = Question(subject_id=subj.id, school_id=school.id, name=str(i+1), question_type="essay", max_score=10)
        db.add(q)
        await db.flush()
        db.add(StudentErrorBook(
            school_id=school.id, student_id="stu_filter", question_id=q.id,
            exam_id=exam.id, student_score=3.0, max_score=10.0,
            mastery_status=status,
        ))
    await db.commit()

    # 按 mastery_status 过滤
    result = await bank_service.get_student_error_book(
        db, student_id="stu_filter", school_id=school.id, mastery_status="unmastered",
    )
    assert len(result) == 2

    # limit
    result = await bank_service.get_student_error_book(
        db, student_id="stu_filter", school_id=school.id, limit=1,
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_student_error_book_empty(db):
    """TG-003: 无错题返回空列表。"""
    result = await bank_service.get_student_error_book(
        db, student_id="nonexistent", school_id="any",
    )
    assert result == []
