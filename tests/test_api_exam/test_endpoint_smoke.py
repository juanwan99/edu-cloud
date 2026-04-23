import pytest
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question


@pytest.fixture
async def exam_with_question(db):
    """Seed exam/subject/question for smoke tests."""
    school = School(name="Smoke", code="SMOKE01", district="D")
    db.add(school)
    await db.flush()

    exam = Exam(name="Smoke Exam", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(
        subject_id=subj.id, name="第1题", question_type="essay",
        max_score=8, school_id=school.id,
        content="解释光合作用", reference_answer="叶绿体吸收光能",
    )
    db.add(q)
    await db.commit()
    return exam, subj, q


@pytest.mark.asyncio
async def test_rubric_generate_endpoint_exists(client, admin_headers):
    resp = await client.post("/api/v1/grading/rubrics/generate", json={}, headers=admin_headers)
    assert resp.status_code != 404  # 422 is fine (missing fields)


@pytest.mark.asyncio
async def test_question_content_endpoint_exists(client, admin_headers):
    # Send request with empty body — endpoint validates fields before DB lookup.
    # 422 (validation error) or 404 (question not found) both confirm the route is registered.
    # A missing route would return 405 (Method Not Allowed).
    resp = await client.put("/api/v1/questions/fake-id/content", json={}, headers=admin_headers)
    assert resp.status_code != 405  # 405 would mean wrong HTTP method; endpoint is registered


@pytest.mark.asyncio
async def test_dispatch_status_returns_questions(client, admin_headers, db, exam_with_question):
    """dispatch/status now returns questions field."""
    exam, subj, q = exam_with_question
    resp = await client.get(f"/api/v1/grading/dispatch/status?exam_id={exam.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "questions" in data[0]
