import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def setup(db):
    school = School(name="排考测试校", code="ES01", district="测试区")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.flush()

    s1 = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    s2 = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    s3 = Subject(exam_id=exam.id, name="英语", code="english", school_id=school.id)
    db.add_all([s1, s2, s3])
    await db.flush()

    user = User(username="director_es", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()

    for obj in [school, exam, s1, s2, s3, user]:
        await db.refresh(obj)

    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {
        "exam": exam, "s1": s1, "s2": s2, "s3": s3,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_set_and_get_schedule(client, setup):
    s = setup
    resp = await client.put(f"/api/v1/exams/{s['exam'].id}/schedule", json={
        "subjects": [
            {"subject_id": s["s1"].id, "exam_start": "2026-04-10T08:00:00", "exam_end": "2026-04-10T10:00:00",
             "exam_room": "301", "proctor_ids": ["t1"]},
            {"subject_id": s["s2"].id, "exam_start": "2026-04-10T10:30:00", "exam_end": "2026-04-10T12:00:00",
             "exam_room": "302"},
        ],
    }, headers=s["headers"])
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    resp = await client.get(f"/api/v1/exams/{s['exam'].id}/schedule", headers=s["headers"])
    assert resp.status_code == 200
    subjects = resp.json()["subjects"]
    scheduled = [sub for sub in subjects if sub["exam_start"] is not None]
    assert len(scheduled) == 2


@pytest.mark.asyncio
async def test_overlap_rejected(client, setup):
    s = setup
    resp = await client.put(f"/api/v1/exams/{s['exam'].id}/schedule", json={
        "subjects": [
            {"subject_id": s["s1"].id, "exam_start": "2026-04-10T08:00:00", "exam_end": "2026-04-10T10:00:00"},
            {"subject_id": s["s2"].id, "exam_start": "2026-04-10T09:00:00", "exam_end": "2026-04-10T11:00:00"},
        ],
    }, headers=s["headers"])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unscheduled_subjects_null(client, setup):
    s = setup
    resp = await client.get(f"/api/v1/exams/{s['exam'].id}/schedule", headers=s["headers"])
    subjects = resp.json()["subjects"]
    assert all(sub["exam_start"] is None for sub in subjects)
