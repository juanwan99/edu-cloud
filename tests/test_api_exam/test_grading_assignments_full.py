"""Integration tests for grading assignment router + service.

Covers:
  POST /api/v1/grading/assignments  (create)
  GET  /api/v1/grading/assignments  (list, requires exam_id)
  GET  /api/v1/grading/progress/{exam_id}  (summary per grader)
  Cross-school isolation, duplicate detection, auth.
"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def grading_setup(db):
    """Seed school + user (academic_director) + exam + subject for assignment tests."""
    school = School(name="阅卷测试校", code="GA01", district="测试区")
    db.add(school)
    await db.flush()

    user = User(username="grading_admin", display_name="阅卷管理员")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="academic_director",
        school_id=school.id, is_primary=True,
    ))
    await db.flush()

    exam = Exam(name="期末语文", school_id=school.id)
    db.add(exam)
    await db.flush()

    subject = Subject(
        exam_id=exam.id, name="语文", code="chinese", school_id=school.id,
    )
    db.add(subject)
    await db.commit()

    token = create_access_token({
        "sub": user.id, "school_id": school.id, "role": "academic_director",
    })
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "school": school,
        "user": user,
        "exam": exam,
        "subject": subject,
        "headers": headers,
    }


def _assignment_payload(setup, **overrides):
    """Build a valid AssignBlockRequest body from the setup fixture."""
    base = {
        "exam_id": setup["exam"].id,
        "subject_id": setup["subject"].id,
        "question_ids": ["q1", "q2"],
        "teacher_id": setup["user"].id,
        "school_id": setup["school"].id,
    }
    base.update(overrides)
    return base


# ── 1. Create assignment ──


@pytest.mark.asyncio
async def test_create_assignment(client, grading_setup):
    """POST /assignments returns 201 with correct fields."""
    payload = _assignment_payload(grading_setup, total_count=30)
    resp = await client.post(
        "/api/v1/grading/assignments",
        json=payload,
        headers=grading_setup["headers"],
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["exam_id"] == grading_setup["exam"].id
    assert data["subject_id"] == grading_setup["subject"].id
    assert data["question_ids"] == ["q1", "q2"]
    assert data["assigned_to"] == grading_setup["user"].id
    assert data["status"] == "pending"
    assert data["total_count"] == 30
    assert data["graded_count"] == 0
    assert data["school_id"] == grading_setup["school"].id


# ── 2. List assignments ──


@pytest.mark.asyncio
async def test_list_assignments(client, grading_setup):
    """GET /assignments?exam_id=... returns created assignments."""
    # Create two assignments with different question sets
    p1 = _assignment_payload(grading_setup, question_ids=["q1"])
    p2 = _assignment_payload(grading_setup, question_ids=["q2"])
    await client.post("/api/v1/grading/assignments", json=p1, headers=grading_setup["headers"])
    await client.post("/api/v1/grading/assignments", json=p2, headers=grading_setup["headers"])

    resp = await client.get(
        f"/api/v1/grading/assignments?exam_id={grading_setup['exam'].id}",
        headers=grading_setup["headers"],
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) == 2
    returned_qids = {tuple(a["question_ids"]) for a in items}
    assert returned_qids == {("q1",), ("q2",)}


# ── 3. Missing exam_id → 422 ──


@pytest.mark.asyncio
async def test_list_assignments_requires_exam_id(client, grading_setup):
    """GET /assignments without exam_id query param → 422 validation error."""
    resp = await client.get(
        "/api/v1/grading/assignments",
        headers=grading_setup["headers"],
    )
    assert resp.status_code == 422


# ── 4. Progress summary ──


@pytest.mark.asyncio
async def test_assignment_progress_summary(client, grading_setup):
    """GET /progress/{exam_id} returns aggregated stats including by_teacher."""
    payload = _assignment_payload(grading_setup, total_count=20)
    await client.post(
        "/api/v1/grading/assignments", json=payload, headers=grading_setup["headers"],
    )

    resp = await client.get(
        f"/api/v1/grading/progress/{grading_setup['exam'].id}",
        headers=grading_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assignments"] == 1
    assert data["pending"] == 1
    assert data["completed"] == 0
    assert data["in_progress"] == 0
    assert data["total_papers"] == 20
    assert data["graded_papers"] == 0
    assert data["progress_pct"] == 0.0
    assert len(data["by_teacher"]) == 1
    teacher = data["by_teacher"][0]
    assert teacher["teacher_id"] == grading_setup["user"].id
    assert teacher["total"] == 20
    assert teacher["graded"] == 0
    assert teacher["questions"] == ["q1", "q2"]


# ── 5. Cross-school isolation ──


@pytest.mark.asyncio
async def test_assignment_wrong_school(client, db, grading_setup):
    """Listing assignments scoped to another school returns empty list."""
    # Create an assignment in school A
    payload = _assignment_payload(grading_setup)
    await client.post(
        "/api/v1/grading/assignments", json=payload, headers=grading_setup["headers"],
    )

    # Create school B + user
    school_b = School(name="另一校", code="GA02", district="测试区")
    db.add(school_b)
    await db.flush()
    user_b = User(username="other_admin", display_name="B 管理员")
    user_b.set_password("test123")
    db.add(user_b)
    await db.flush()
    db.add(UserRole(
        user_id=user_b.id, role="academic_director",
        school_id=school_b.id, is_primary=True,
    ))
    await db.commit()

    token_b = create_access_token({
        "sub": user_b.id, "school_id": school_b.id, "role": "academic_director",
    })
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B queries same exam → should see nothing (school_id filter)
    resp = await client.get(
        f"/api/v1/grading/assignments?exam_id={grading_setup['exam'].id}",
        headers=headers_b,
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ── 6. Duplicate assignment (overlapping questions) → 409 ──


@pytest.mark.asyncio
async def test_create_duplicate_assignment(client, grading_setup):
    """Creating assignment with overlapping question_ids → 409 ConflictError."""
    payload = _assignment_payload(grading_setup, question_ids=["q1", "q2"])
    resp1 = await client.post(
        "/api/v1/grading/assignments", json=payload, headers=grading_setup["headers"],
    )
    assert resp1.status_code == 201

    # Same questions again → conflict
    resp2 = await client.post(
        "/api/v1/grading/assignments", json=payload, headers=grading_setup["headers"],
    )
    assert resp2.status_code == 409
    assert "already assigned" in resp2.json()["detail"]


# ── 7. Partial overlap still triggers conflict ──


@pytest.mark.asyncio
async def test_partial_overlap_conflict(client, grading_setup):
    """Assigning questions with partial overlap → 409."""
    p1 = _assignment_payload(grading_setup, question_ids=["q1", "q2"])
    resp1 = await client.post(
        "/api/v1/grading/assignments", json=p1, headers=grading_setup["headers"],
    )
    assert resp1.status_code == 201

    # q2 overlaps with the first assignment
    p2 = _assignment_payload(grading_setup, question_ids=["q2", "q3"])
    resp2 = await client.post(
        "/api/v1/grading/assignments", json=p2, headers=grading_setup["headers"],
    )
    assert resp2.status_code == 409


# ── 8. Progress on empty exam ──


@pytest.mark.asyncio
async def test_progress_empty_exam(client, grading_setup):
    """Progress for exam with no assignments returns zeroed stats."""
    resp = await client.get(
        f"/api/v1/grading/progress/{grading_setup['exam'].id}",
        headers=grading_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assignments"] == 0
    assert data["total_papers"] == 0
    assert data["graded_papers"] == 0
    assert data["progress_pct"] == 0.0
    assert data["by_teacher"] == []
