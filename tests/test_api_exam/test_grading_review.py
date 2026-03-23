import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, AIGradingResult
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def review_setup(client, db):
    school = School(name="RV", code="RV01")
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
    subject = Subject(exam_id=exam.id, name="语文", code="ch", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(subject_id=subject.id, name="Q1", question_type="subjective", max_score=10.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="completed", total=2, completed=2, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    answers = []
    results = []
    for i in range(2):
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=f"s{i}",
            question_id=q.id, image_path=f"/fake/{i}.png", school_id=school.id,
        )
        db.add(a)
        await db.commit()
        r = AIGradingResult(
            task_id=task.id, answer_id=a.id, question_id=q.id,
            school_id=school.id, score=8.0, max_score=10.0,
            feedback="不错", confidence=0.9, review_status="pending",
        )
        db.add(r)
        results.append(r)
    await db.commit()

    return {
        "headers": headers, "task_id": task.id, "user_id": user.id,
        "result_ids": [r.id for r in results], "school_id": school.id,
    }


async def test_list_results_by_task(client, review_setup):
    resp = await client.get(
        f"/api/v1/grading/results?task_id={review_setup['task_id']}",
        headers=review_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(r["review_status"] == "pending" for r in data)


async def test_get_single_result(client, review_setup):
    rid = review_setup["result_ids"][0]
    resp = await client.get(f"/api/v1/grading/results/{rid}", headers=review_setup["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == rid


async def test_approve_result(client, review_setup):
    rid = review_setup["result_ids"][0]
    resp = await client.post(
        f"/api/v1/grading/review/{rid}",
        json={"action": "approve"},
        headers=review_setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "approved"


async def test_override_result(client, review_setup):
    rid = review_setup["result_ids"][1]
    resp = await client.post(
        f"/api/v1/grading/review/{rid}",
        json={"action": "override", "adjusted_score": 6.0, "comment": "扣分"},
        headers=review_setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "overridden"
    assert resp.json()["adjusted_score"] == 6.0


async def test_override_without_score_rejected(client, review_setup):
    rid = review_setup["result_ids"][0]
    resp = await client.post(
        f"/api/v1/grading/review/{rid}",
        json={"action": "override"},
        headers=review_setup["headers"],
    )
    assert resp.status_code == 400


async def test_duplicate_review_rejected(client, review_setup):
    rid = review_setup["result_ids"][0]
    resp1 = await client.post(
        f"/api/v1/grading/review/{rid}",
        json={"action": "approve"},
        headers=review_setup["headers"],
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        f"/api/v1/grading/review/{rid}",
        json={"action": "override", "adjusted_score": 5.0},
        headers=review_setup["headers"],
    )
    assert resp2.status_code == 409


async def test_list_pending_reviews(client, review_setup):
    resp = await client.get("/api/v1/grading/review/pending", headers=review_setup["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # both are pending initially
