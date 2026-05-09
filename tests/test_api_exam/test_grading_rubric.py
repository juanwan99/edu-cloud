import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def rubric_setup(client, db):
    school = School(name="RS", code="RS01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "academic_director"})
    headers = {"Authorization": f"Bearer {token}"}
    exam = Exam(name="E", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(
        subject_id=subject.id, name="解释词语", question_type="essay",
        max_score=10.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()

    # Create another school for cross-tenant test
    other_school = School(name="Other", code="OT01")
    db.add(other_school)
    await db.commit()
    other_q = Question(
        subject_id=subject.id, name="其他题", question_type="essay",
        max_score=5.0, school_id=other_school.id,
    )
    db.add(other_q)
    await db.commit()

    return {"headers": headers, "question_id": q.id, "other_question_id": other_q.id, "school_id": school.id}


async def test_create_rubric(client, rubric_setup):
    resp = await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_setup["question_id"],
            "criteria": [
                {"blankNo": "1", "score": 5.0, "answer": "正确表述概念", "intent": "考查", "coreRequirement": "必须"},
                {"blankNo": "2", "score": 5.0, "answer": "延伸分析", "intent": "考查", "coreRequirement": "必须"},
            ],
            "reference_answer": "标准答案",
            "source": "manual",
        },
        headers=rubric_setup["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["question_id"] == rubric_setup["question_id"]
    assert data["source"] == "manual"
    assert len(data["criteria"]) == 2


async def test_get_rubric(client, rubric_setup):
    # Create first
    await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_setup["question_id"],
            "criteria": [{"blankNo": "1", "score": 10.0, "answer": "要点答案", "intent": "考查", "coreRequirement": "必须"}],
            "source": "manual",
        },
        headers=rubric_setup["headers"],
    )
    resp = await client.get(
        f"/api/v1/grading/rubrics/{rubric_setup['question_id']}",
        headers=rubric_setup["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["criteria"][0]["blankNo"] == "1"


async def test_get_rubric_not_found(client, rubric_setup):
    resp = await client.get(
        "/api/v1/grading/rubrics/nonexistent",
        headers=rubric_setup["headers"],
    )
    # Endpoint returns 200 with null body when rubric not found
    assert resp.status_code == 200
    assert resp.json() is None


async def test_create_rubric_duplicate_updates(client, rubric_setup):
    body = {
        "question_id": rubric_setup["question_id"],
        "criteria": [
            {"blankNo": "1", "score": 5.0, "answer": "v1 答案", "intent": "test", "coreRequirement": "必须"},
            {"blankNo": "2", "score": 5.0, "answer": "v1 补充", "intent": "test", "coreRequirement": "必须"},
        ],
        "source": "manual",
    }
    resp1 = await client.post("/api/v1/grading/rubrics", json=body, headers=rubric_setup["headers"])
    assert resp1.status_code == 201

    body["criteria"] = [{"blankNo": "1", "score": 10.0, "answer": "v2 答案", "intent": "test", "coreRequirement": "必须"}]
    resp2 = await client.post("/api/v1/grading/rubrics", json=body, headers=rubric_setup["headers"])
    assert resp2.status_code == 201  # upsert returns 201
    assert resp2.json()["criteria"][0]["answer"] == "v2 答案"


async def test_cross_tenant_rubric_blocked(client, rubric_setup):
    resp = await client.get(
        f"/api/v1/grading/rubrics/{rubric_setup['other_question_id']}",
        headers=rubric_setup["headers"],
    )
    # Cross-tenant rubric returns 200 null (filtered by school_id, not found)
    assert resp.status_code == 200
    assert resp.json() is None
