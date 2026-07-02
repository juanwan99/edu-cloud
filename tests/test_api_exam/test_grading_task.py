import pytest
from unittest.mock import patch, AsyncMock
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, Rubric
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
        subject_id=subject.id, name="Q1", question_type="essay",
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

    return {"headers": headers, "subject_id": subject.id, "question_id": q.id, "school_id": school.id}


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


async def test_batch_grading_task_rejects_unreadable_running_question_ids(client, task_grading_setup, db):
    """Bad legacy question_ids must not bypass the running-task overlap guard."""
    from sqlalchemy import select as _select

    existing = GradingTask(
        subject_id=task_grading_setup["subject_id"],
        question_ids="not-json",
        school_id=task_grading_setup["school_id"],
        status="processing",
        created_by="legacy-user",
    )
    db.add(existing)
    await db.commit()

    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock) as enqueue:
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={
                "subject_id": task_grading_setup["subject_id"],
                "question_ids": [task_grading_setup["question_id"]],
            },
            headers=task_grading_setup["headers"],
        )

    assert resp.status_code == 409
    assert "unreadable question_ids" in resp.json().get("detail", "")
    enqueue.assert_not_called()

    tasks = (await db.execute(
        _select(GradingTask).where(GradingTask.subject_id == task_grading_setup["subject_id"])
    )).scalars().all()
    assert [task.id for task in tasks] == [existing.id]


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


# ---------- F007 前置校验 + orphan task 防御（B3a）----------

@pytest.fixture
async def grading_setup_no_rubric(client, db):
    """包含 subject + subjective question + answers，但缺 Rubric。"""
    school = School(name="NR", code="NR01")
    db.add(school)
    await db.commit()
    user = User(username="nr_u", display_name="U")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "academic_director"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="NRExam", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(
        subject_id=subject.id, name="Q1", question_type="essay",
        max_score=10.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()
    a = StudentAnswer(
        exam_id=exam.id, subject_id=subject.id, student_id="s0",
        question_id=q.id, image_path="/fake/0.png", school_id=school.id,
    )
    db.add(a)
    await db.commit()
    return {"headers": headers, "subject_id": subject.id}


@pytest.fixture
async def grading_setup_no_answers(client, db):
    """包含 subject + subjective question + rubric，但缺 StudentAnswer。"""
    school = School(name="NA", code="NA01")
    db.add(school)
    await db.commit()
    user = User(username="na_u", display_name="U")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "academic_director"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="NAExam", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(
        subject_id=subject.id, name="Q1", question_type="essay",
        max_score=10.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()
    rubric = Rubric(
        question_id=q.id, school_id=school.id, source="manual",
        criteria=[{"point": "p", "score": 10.0, "description": "d"}],
    )
    db.add(rubric)
    await db.commit()
    return {"headers": headers, "subject_id": subject.id}


@pytest.fixture
async def grading_setup_no_subjective(client, db):
    """包含 subject 但所有 question 都是客观题。"""
    school = School(name="NS", code="NS01")
    db.add(school)
    await db.commit()
    user = User(username="ns_u", display_name="U")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "academic_director"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="NSExam", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(
        subject_id=subject.id, name="Q1", question_type="choice",
        max_score=5.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()
    return {"headers": headers, "subject_id": subject.id}


async def test_create_grading_task_rejects_no_subjective_questions(client, grading_setup_no_subjective):
    """F007 回归：只有客观题时拒绝创建 AI 阅卷任务（400）。

    反例：错误实现会 commit GradingTask + enqueue，worker 跑到 L72 trivially completed=0
    """
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": grading_setup_no_subjective["subject_id"]},
            headers=grading_setup_no_subjective["headers"],
        )
    assert resp.status_code == 400
    assert "主观题" in resp.json().get("detail", "")


async def test_create_grading_task_rejects_no_rubric(client, grading_setup_no_rubric):
    """F007 回归：主观题缺 Rubric 时拒绝（400）。

    反例：错误实现会 enqueue 后 worker L120 全部 failed，用户看到 task failed 但不知原因
    """
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": grading_setup_no_rubric["subject_id"]},
            headers=grading_setup_no_rubric["headers"],
        )
    assert resp.status_code == 400
    assert "评分标准" in resp.json().get("detail", "") or "rubric" in resp.json().get("detail", "").lower()


async def test_create_grading_task_rejects_no_answers(client, grading_setup_no_answers):
    """F007 回归：无 StudentAnswer 时拒绝（400）。

    反例：错误实现 worker 跑完 total=0，task 看起来成功但什么都没做
    """
    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": grading_setup_no_answers["subject_id"]},
            headers=grading_setup_no_answers["headers"],
        )
    assert resp.status_code == 400
    assert "答卷" in resp.json().get("detail", "") or "answer" in resp.json().get("detail", "").lower()


async def test_create_grading_task_cleans_up_orphan_on_enqueue_failure(client, task_grading_setup, db):
    """F007 orphan 防御回归：enqueue Redis 失败时，已创建的 GradingTask 必须被清理 + 返回 503。

    反例：错误实现（当前）在 L172 commit 后才 enqueue，Redis 挂时产生 orphan GradingTask。
    本测试构造 enqueue 抛 ConnectionError → 预期响应 503 + DB 无 pending task 残留
    """
    from edu_cloud.modules.grading.models import GradingTask
    from sqlalchemy import select as _select

    async def boom(*args, **kwargs):
        raise ConnectionError("Redis unreachable")

    with patch("edu_cloud.modules.grading.router.enqueue_grading_task", side_effect=boom):
        resp = await client.post(
            "/api/v1/grading/tasks",
            json={"subject_id": task_grading_setup["subject_id"]},
            headers=task_grading_setup["headers"],
        )

    assert resp.status_code == 503, f"预期 503 Queue unavailable, 实际 {resp.status_code}"

    # DB 无 orphan task
    tasks = (await db.execute(_select(GradingTask).where(
        GradingTask.subject_id == task_grading_setup["subject_id"]
    ))).scalars().all()
    assert len(tasks) == 0, f"预期 0 个 task（已清理 orphan），实际 {len(tasks)} 个"
