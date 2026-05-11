"""P-001: _upsert_ai_result must reject writing to confirmed records."""
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.workers.grading import _upsert_ai_result


@pytest.fixture
async def isolation_setup(db):
    """Minimal chain: school -> exam -> subject -> question -> answer -> task + confirmed result."""
    school = School(name="IsoSchool", code="ISO01")
    db.add(school)
    await db.commit()

    user = User(username="iso_teacher", display_name="IsoTeacher")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="IsoExam", school_id=school.id)
    db.add(exam)
    await db.commit()

    subject = Subject(exam_id=exam.id, name="Math", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()

    question = Question(
        subject_id=subject.id, name="Q1", question_type="essay",
        max_score=10.0, school_id=school.id,
    )
    db.add(question)
    await db.commit()

    answer = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id="stu_iso",
        question_id=question.id, image_path="/fake/iso.png", school_id=school.id,
    )
    db.add(answer)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="pending", total=1, completed=0, failed=0,
        created_by=user.id,
    )
    db.add(task)
    await db.commit()

    # Pre-existing confirmed manual result (teacher already scored this)
    result = GradingResult(
        answer_id=answer.id,
        question_id=question.id,
        school_id=school.id,
        status="confirmed",
        source="manual",
        final_score=8.0,
        max_score=10.0,
        ai_score=None,
        ai_feedback=None,
        ai_raw_response=None,
        version=1,
    )
    db.add(result)
    await db.commit()

    return {
        "task": task,
        "answer_id": answer.id,
        "question_id": question.id,
        "result_id": result.id,
    }


async def test_upsert_ai_result_skips_confirmed_record(db, isolation_setup):
    """_upsert_ai_result must NOT overwrite a confirmed manual record."""
    setup = isolation_setup
    result_dict = {
        "answer_id": setup["answer_id"],
        "question_id": setup["question_id"],
        "score": 7.5,
        "confidence": 0.9,
        "feedback": "AI feedback that should be rejected",
        "max_score": 10.0,
    }

    status = await _upsert_ai_result(db, setup["task"], result_dict)
    await db.commit()

    assert status == "skipped_confirmed"

    # Verify the record is unchanged
    row = (await db.execute(
        select(GradingResult).where(GradingResult.id == setup["result_id"])
    )).scalar_one()

    assert row.ai_score is None, "ai_score must remain None for confirmed manual record"
    assert row.ai_feedback is None, "ai_feedback must remain None"
    assert row.ai_raw_response is None, "ai_raw_response must remain None"
    assert row.source == "manual", "source must stay manual"
    assert row.status == "confirmed", "status must stay confirmed"
    assert row.final_score == 8.0, "final_score must stay at teacher's score"
    assert row.version == 1, "version must not increment"
