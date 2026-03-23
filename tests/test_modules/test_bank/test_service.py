"""Bank 服务测试 — TG-01 修复。"""
import pytest
from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook
from edu_cloud.modules.bank.service import (
    get_bank_question, list_bank_questions, get_student_error_book, get_error_book_stats,
)
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.services.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_list_bank_questions_empty(db):
    """空题库返回空列表。"""
    school = School(name="BK", code="BK01", district="X")
    db.add(school)
    await db.flush()
    result = await list_bank_questions(db, school_id=school.id)
    assert result == []


@pytest.mark.asyncio
async def test_get_bank_question_not_found(db):
    """不存在的题库题目 → NotFoundError。"""
    school = School(name="NF", code="NF01", district="X")
    db.add(school)
    await db.flush()
    with pytest.raises(NotFoundError):
        await get_bank_question(db, bank_question_id="nonexistent", school_id=school.id)


@pytest.mark.asyncio
async def test_list_bank_questions_school_filter(db):
    """题库查询只返回本校。"""
    s1 = School(name="BK_A", code="BK_A", district="X")
    s2 = School(name="BK_B", code="BK_B", district="X")
    db.add_all([s1, s2])
    await db.flush()
    exam = Exam(name="BK考", school_id=s1.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="语文", code="YW", school_id=s1.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, name="题1", question_type="objective", max_score=5, school_id=s1.id)
    db.add(q)
    await db.flush()
    bq = BankQuestion(
        school_id=s1.id, question_type="objective", max_score=5,
        source_exam_id=exam.id, source_question_id=q.id,
    )
    db.add(bq)
    await db.commit()

    result_a = await list_bank_questions(db, school_id=s1.id)
    result_b = await list_bank_questions(db, school_id=s2.id)
    assert len(result_a) == 1
    assert len(result_b) == 0


@pytest.mark.asyncio
async def test_error_book_stats_empty(db):
    """无错题时统计全零。"""
    school = School(name="EB", code="EB01", district="X")
    db.add(school)
    await db.flush()
    stats = await get_error_book_stats(db, student_id="nonexistent", school_id=school.id)
    assert stats["total"] == 0
    assert stats["unmastered"] == 0


@pytest.mark.asyncio
async def test_error_book_stats_with_data(db):
    """有错题时统计正确。"""
    school = School(name="EBS", code="EBS01", district="X")
    db.add(school)
    await db.flush()
    exam = Exam(name="EBS考", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q1 = Question(subject_id=subj.id, name="题1", question_type="subjective", max_score=10, school_id=school.id)
    q2 = Question(subject_id=subj.id, name="题2", question_type="subjective", max_score=10, school_id=school.id)
    db.add_all([q1, q2])
    await db.flush()
    db.add(StudentErrorBook(
        student_id="stu1", question_id=q1.id, exam_id=exam.id,
        student_score=3, max_score=10, mastery_status="unmastered", school_id=school.id,
    ))
    db.add(StudentErrorBook(
        student_id="stu1", question_id=q2.id, exam_id=exam.id,
        student_score=7, max_score=10, mastery_status="practicing", school_id=school.id,
    ))
    await db.commit()
    stats = await get_error_book_stats(db, student_id="stu1", school_id=school.id)
    assert stats["total"] == 2
    assert stats["unmastered"] == 1
    assert stats["practicing"] == 1
