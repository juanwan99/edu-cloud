import pytest
from edu_cloud.modules.exam.models import Exam


@pytest.mark.asyncio
async def test_publish_exam(client, admin_headers, db):
    exam = Exam(name="Publish Test", status="completed", school_id="test-school-id")
    db.add(exam)
    await db.flush()

    resp = await client.post(
        f"/api/v1/exams/{exam.id}/publish",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_archive_exam(client, admin_headers, db):
    exam = Exam(name="Archive Test", status="published", school_id="test-school-id")
    db.add(exam)
    await db.flush()

    resp = await client.post(
        f"/api/v1/exams/{exam.id}/archive",
        headers=admin_headers,
    )
    assert resp.status_code == 200
