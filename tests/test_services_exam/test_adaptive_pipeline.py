"""验证 exam.published 事件触发 adaptive mastery 更新。"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_on_exam_published_calls_adaptive_mastery():
    """on_exam_published 应调用模块外服务 update_adaptive_mastery（D-03E）。"""
    with patch("edu_cloud.services.post_exam_adaptive.update_adaptive_mastery", new_callable=AsyncMock) as mock_adaptive, \
         patch("edu_cloud.modules.pipeline.service.update_knowledge_mastery", new_callable=AsyncMock, return_value=0), \
         patch("edu_cloud.modules.pipeline.service.update_error_patterns", new_callable=AsyncMock, return_value=0), \
         patch("edu_cloud.database.async_session") as mock_session_factory:

        mock_adaptive.return_value = 10

        mock_db = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        from edu_cloud.modules.pipeline import on_exam_published
        await on_exam_published({"exam_id": "test-exam", "school_id": "test-school"})

        mock_adaptive.assert_called_once_with(mock_db, exam_id="test-exam", school_id="test-school")


@pytest.mark.asyncio
async def test_on_exam_published_missing_payload():
    """缺少 exam_id 或 school_id 时应直接返回。"""
    from edu_cloud.modules.pipeline import on_exam_published
    # 不应抛异常
    await on_exam_published({})
    await on_exam_published({"exam_id": "x"})
    await on_exam_published({"school_id": "x"})


@pytest.mark.asyncio
async def test_update_adaptive_mastery_uses_canonical_student_identity(db):
    """UUID、学号、条码混合作答时，adaptive 只写 canonical Student.id。"""
    from edu_cloud.models.school import School
    from edu_cloud.modules.adaptive.models import AnswerLog, DaKnowledgePointMap, StudentDaMastery
    from edu_cloud.modules.exam.models import Exam, Question, Subject
    from edu_cloud.modules.grading.models import GradingResult
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.student.models import Class, Student
    from edu_cloud.services.post_exam_adaptive import update_adaptive_mastery

    school = School(name="Adaptive Identity School", code="ADAPT_ID")
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

    subject = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subject)
    await db.flush()

    questions = [
        Question(
            subject_id=subject.id,
            school_id=school.id,
            name="1",
            question_type="choice",
            max_score=3.0,
        ),
        Question(
            subject_id=subject.id,
            school_id=school.id,
            name="2",
            question_type="choice",
            max_score=3.0,
        ),
        Question(
            subject_id=subject.id,
            school_id=school.id,
            name="12",
            question_type="essay",
            max_score=10.0,
        ),
    ]
    db.add_all(questions)
    await db.flush()

    kp = ConceptGraphNode(
        id="ADAPT_IDENT_KP",
        name="函数",
        knowledge_level="L1",
        primary_module="M1",
        synced_at=datetime.now(timezone.utc),
        course_code="SX",
    )
    db.add(kp)
    await db.flush()

    db.add(DaKnowledgePointMap(da_id="ADAPT_IDENT_DA", knowledge_point_id=kp.id, weight=1.0))
    db.add_all([
        QuestionKnowledgePoint(question_id=question.id, concept_id=kp.id)
        for question in questions
    ])
    await db.flush()

    uuid_answer = StudentAnswer(
        exam_id=exam.id,
        subject_id=subject.id,
        student_id=student.id,
        question_id=questions[0].id,
        school_id=school.id,
        score=3.0,
    )
    number_answer = StudentAnswer(
        exam_id=exam.id,
        subject_id=subject.id,
        student_id=student.student_number,
        question_id=questions[1].id,
        school_id=school.id,
        score=2.0,
    )
    barcode_answer = StudentAnswer(
        exam_id=exam.id,
        subject_id=subject.id,
        student_id="250101",
        question_id=questions[2].id,
        school_id=school.id,
        score=None,
    )
    db.add_all([uuid_answer, number_answer, barcode_answer])
    await db.flush()

    db.add(GradingResult(
        answer_id=barcode_answer.id,
        question_id=questions[2].id,
        school_id=school.id,
        final_score=9.0,
        max_score=10.0,
        status="confirmed",
        source="manual",
    ))
    await db.commit()

    processed = await update_adaptive_mastery(db, exam_id=exam.id, school_id=school.id)

    assert processed == 3
    logs = (await db.execute(
        select(AnswerLog).where(
            AnswerLog.exam_id == exam.id,
            AnswerLog.school_id == school.id,
        )
    )).scalars().all()
    assert len(logs) == 3
    assert {log.student_id for log in logs} == {student.id}
    assert {log.question_id for log in logs} == {question.id for question in questions}

    masteries = (await db.execute(
        select(StudentDaMastery).where(
            StudentDaMastery.school_id == school.id,
            StudentDaMastery.da_id == "ADAPT_IDENT_DA",
        )
    )).scalars().all()
    assert len(masteries) == 1
    assert masteries[0].student_id == student.id
    assert masteries[0].attempt_count == 3

    processed_again = await update_adaptive_mastery(db, exam_id=exam.id, school_id=school.id)
    assert processed_again == 0

    logs_again = (await db.execute(
        select(AnswerLog).where(
            AnswerLog.exam_id == exam.id,
            AnswerLog.school_id == school.id,
        )
    )).scalars().all()
    assert len(logs_again) == 3

    masteries_again = (await db.execute(
        select(StudentDaMastery).where(
            StudentDaMastery.school_id == school.id,
            StudentDaMastery.da_id == "ADAPT_IDENT_DA",
        )
    )).scalars().all()
    assert len(masteries_again) == 1
    assert masteries_again[0].attempt_count == 3
