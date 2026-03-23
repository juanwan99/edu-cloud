"""Exam 模块模型 CRUD + school_id 隔离测试。"""
import pytest
from edu_cloud.modules.exam.models import Exam, Subject, Question, ExamResult
from edu_cloud.models.school import School
from edu_cloud.models.student import Student


@pytest.mark.asyncio
async def test_exam_crud(db):
    """Exam 基础 CRUD。"""
    school = School(name="考试校", code="EX01", district="X")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", card_title="2026期中", school_id=school.id)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    assert exam.id is not None
    assert exam.name == "期中考试"
    assert exam.status == "draft"
    assert exam.school_id == school.id


@pytest.mark.asyncio
async def test_subject_unique_per_exam(db):
    """同一考试内 subject code 唯一。"""
    school = School(name="科目校", code="SU01", district="X")
    db.add(school)
    await db.flush()

    exam = Exam(name="测试考试", school_id=school.id)
    db.add(exam)
    await db.flush()

    s1 = Subject(exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    db.add(s1)
    await db.commit()

    s2 = Subject(exam_id=exam.id, name="语文重复", code="YW", school_id=school.id)
    db.add(s2)
    with pytest.raises(Exception):  # IntegrityError
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_question_crud(db):
    """Question 基础创建。"""
    school = School(name="题目校", code="QU01", district="X")
    db.add(school)
    await db.flush()

    exam = Exam(name="测试", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(
        subject_id=subj.id, name="选择题1", question_type="objective",
        max_score=5.0, correct_answer="B", school_id=school.id,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    assert q.question_type == "objective"
    assert q.correct_answer == "B"


@pytest.mark.asyncio
async def test_exam_school_isolation(db):
    """不同学校的考试互不可见（模型层验证 school_id 存在）。"""
    s1 = School(name="校A", code="ISO_A", district="X")
    s2 = School(name="校B", code="ISO_B", district="X")
    db.add_all([s1, s2])
    await db.flush()

    e1 = Exam(name="校A考试", school_id=s1.id)
    e2 = Exam(name="校B考试", school_id=s2.id)
    db.add_all([e1, e2])
    await db.commit()

    from sqlalchemy import select
    result = await db.execute(
        select(Exam).where(Exam.school_id == s1.id)
    )
    exams = result.scalars().all()
    assert len(exams) == 1
    assert exams[0].name == "校A考试"


@pytest.mark.asyncio
async def test_exam_result_preserved(db):
    """ExamResult 聚合视图模型仍可正常使用。"""
    school = School(name="成绩校", code="RES01", district="X")
    db.add(school)
    await db.flush()

    exam = Exam(name="成绩测试", school_id=school.id, subject_code="SX", max_score=150)
    db.add(exam)
    await db.flush()

    student = Student(name="张三", student_number="S001", school_id=school.id, grade="七年级")
    db.add(student)
    await db.flush()

    result = ExamResult(
        exam_id=exam.id, student_id=student.id,
        school_id=school.id, total_score=120.5,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)

    assert result.total_score == 120.5
