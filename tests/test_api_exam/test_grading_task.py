import pytest
from unittest.mock import patch, AsyncMock
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def task_grading_setup(client, db):
    school = School(name="TS", code="TS01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "teacher"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="E", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()

    q = Question(
        subject_id=subject.id, name="Q1", question_type="subjective",
        max_score=10.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()

    # Add rubric
    rubric = Rubric(
        question_id=q.id, school_id=school.id, source="manual",
        criteria=[{"point": "p", "score": 10.0, "description": "d"}],
    )
    db.add(rubric)
    await db.commit()

    # Add answers
    for i in range(2):
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=f"s{i}",
            question_id=q.id, image_path=f"/fake/{i}.png", school_id=school.id,
        )
        db.add(a)
    await db.commit()

    return {"headers": headers, "subject_id": subject.id, "school_id": school.id}


async def test_create_grading_task(client, task_grading_setup):
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": task_grading_setup["subject_id"]},
            headers=task_grading_setup["headers"],
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["subject_id"] == task_grading_setup["subject_id"]
    assert "id" in data


async def test_create_grading_task_invalid_subject(client, task_grading_setup):
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": "nonexistent"},
            headers=task_grading_setup["headers"],
        )
    assert resp.status_code == 404


async def test_get_grading_task(client, task_grading_setup):
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        create_resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": task_grading_setup["subject_id"]},
            headers=task_grading_setup["headers"],
        )
    task_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/grading/tasks/{task_id}", headers=task_grading_setup["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


async def test_get_grading_task_not_found(client, task_grading_setup):
    resp = await client.get("/api/v1/grading/tasks/nonexistent", headers=task_grading_setup["headers"])
    assert resp.status_code == 404
