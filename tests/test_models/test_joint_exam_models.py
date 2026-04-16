import pytest
from edu_cloud.models.joint_exam import (
    JointExam, JointExamParticipant, JointExamStudentResult,
)


@pytest.mark.asyncio
async def test_joint_exam_new_fields(db):
    exam = JointExam(
        name="测试联考",
        created_by="user-id",
        status="draft",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id="school-id",
        answer_detail_schema={"YW": [{"id": "q1", "max_score": 10}]},
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    assert exam.creator_school_id == "school-id"
    assert exam.answer_detail_schema["YW"][0]["id"] == "q1"


@pytest.mark.asyncio
async def test_participant_is_creator(db):
    exam = JointExam(name="E", created_by="u", status="draft", subjects=[])
    db.add(exam)
    await db.commit()

    p = JointExamParticipant(
        joint_exam_id=exam.id, school_id="s1", is_creator=True,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    assert p.is_creator is True
    assert p.status == "pending"


@pytest.mark.asyncio
async def test_student_result_create(db):
    exam = JointExam(name="E", created_by="u", status="draft", subjects=[])
    db.add(exam)
    await db.commit()

    result = JointExamStudentResult(
        joint_exam_id=exam.id,
        school_id="s1",
        subject_code="YW",
        student_name="张三",
        student_number="2026001",
        total_score=85.5,
        detail_scores=[{"question_id": "q1", "score": 8, "max_score": 10}],
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    assert result.total_score == 85.5
    assert result.detail_scores[0]["question_id"] == "q1"
