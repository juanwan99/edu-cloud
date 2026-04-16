import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.workers.grading import process_grading_task
from edu_cloud.modules.grading.llm_client import GradeResponse


@pytest.fixture
async def grading_setup(db):
    """Create full data chain: school→user→exam→subject→question→rubric→answers→task."""
    school = School(name="GS", code="GS01")
    db.add(school)
    await db.commit()

    user = User(username="teacher", display_name="Teacher")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id)
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

    rubric = Rubric(
        question_id=q.id, school_id=school.id, source="manual",
        criteria=[{"point": "解释准确", "score": 5.0, "description": "含义正确"},
                  {"point": "举例恰当", "score": 5.0, "description": "有实例"}],
    )
    db.add(rubric)
    await db.commit()

    answers = []
    for i in range(3):
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=f"stu_{i}",
            question_id=q.id, image_path=f"/fake/path/{i}.png", school_id=school.id,
        )
        db.add(a)
        answers.append(a)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="pending", total=3, completed=0, failed=0,
        created_by=user.id,
    )
    db.add(task)
    await db.commit()

    return {"task_id": task.id, "school_id": school.id, "question_id": q.id}


async def test_process_grading_task_routes_question_type_to_llm(db_engine, db, grading_setup):
    """Phase 1-C: StudentAnswer.question_type 应作为 question_type 参数透传给 LLM.grade。"""
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ctx = {"db_session_factory": sf}

    # 把 3 个 answer 的 question_type 设成不同值
    async with sf() as session:
        rows = (await session.execute(select(StudentAnswer))).scalars().all()
        rows[0].question_type = "fill_blank"
        rows[1].question_type = "essay"
        rows[2].question_type = None  # 测试 fallback 到 Question.question_type
        await session.commit()

    captured_qtypes = []

    async def mock_grade_fn(*args, **kwargs):
        captured_qtypes.append(kwargs.get("question_type"))
        return GradeResponse(score=5.0, max_score=10.0, feedback="ok", confidence=0.9)

    mock_client = AsyncMock()
    mock_client.grade = AsyncMock(side_effect=mock_grade_fn)
    mock_client.close = AsyncMock()

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="fakebase64"):
        with patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_client):
            await process_grading_task(ctx, grading_setup["task_id"])

    # 顺序未保证，但应包含 fill_blank、essay、essay（None 回落到 Question.question_type='essay'）
    assert sorted(captured_qtypes) == ["essay", "essay", "fill_blank"]


async def test_process_grading_task_success(db_engine, db, grading_setup):
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ctx = {"db_session_factory": sf}

    mock_grade = GradeResponse(score=8.0, max_score=10.0, feedback="不错", confidence=0.9)
    mock_client = AsyncMock()
    mock_client.grade = AsyncMock(return_value=mock_grade)
    mock_client.close = AsyncMock()

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="fakebase64"):
        with patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_client):
            await process_grading_task(ctx, grading_setup["task_id"])

    # Reload task in a fresh session to see committed data
    async with sf() as session:
        result = await session.execute(select(GradingTask).where(GradingTask.id == grading_setup["task_id"]))
        task = result.scalar_one()
        assert task.status == "completed"
        assert task.completed == 3
        assert task.failed == 0

        # Check results created
        results = await session.execute(select(GradingResult).where(GradingResult.ai_task_id == task.id))
        grading_results = results.scalars().all()
        assert len(grading_results) == 3
        for r in grading_results:
            assert r.ai_score == 8.0
            assert r.final_score == 8.0  # 初始 final = ai_score
            assert r.status == "ai_done"
            assert r.source is None  # 待教师审核


async def test_process_grading_task_partial_failure(db_engine, db, grading_setup):
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ctx = {"db_session_factory": sf}

    call_count = 0

    async def mock_grade_fn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("LLM timeout")
        return GradeResponse(score=7.0, max_score=10.0, feedback="ok", confidence=0.8)

    mock_client = AsyncMock()
    mock_client.grade = AsyncMock(side_effect=mock_grade_fn)
    mock_client.close = AsyncMock()

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="fakebase64"):
        with patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_client):
            await process_grading_task(ctx, grading_setup["task_id"])

    async with sf() as session:
        result = await session.execute(select(GradingTask).where(GradingTask.id == grading_setup["task_id"]))
        task = result.scalar_one()
        assert task.completed == 2
        assert task.failed == 1
        assert task.status == "failed"
        assert task.error_log is not None
        assert len(task.error_log) == 1


# ── Batch concurrency tests ──────────────────────────────────────


@pytest.fixture
async def grading_setup_25(db):
    """Create 25 answers (> batch_size=20) to test batching."""
    school = School(name="BatchSchool", code="BS01")
    db.add(school)
    await db.commit()

    user = User(username="batch_teacher", display_name="BatchTeacher")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="批量测试", school_id=school.id)
    db.add(exam)
    await db.commit()

    subject = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()

    q = Question(
        subject_id=subject.id, name="计算题", question_type="essay",
        max_score=10.0, school_id=school.id,
    )
    db.add(q)
    await db.commit()

    rubric = Rubric(
        question_id=q.id, school_id=school.id, source="manual",
        criteria=[{"point": "正确", "score": 10.0, "description": "计算正确"}],
    )
    db.add(rubric)
    await db.commit()

    for i in range(25):
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=f"stu_{i}",
            question_id=q.id, image_path=f"/fake/path/{i}.png", school_id=school.id,
        )
        db.add(a)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="pending", total=0, completed=0, failed=0,
        created_by=user.id,
    )
    db.add(task)
    await db.commit()

    return {"task_id": task.id, "school_id": school.id, "question_id": q.id}


async def test_batch_concurrency_25_answers(db_engine, db, grading_setup_25):
    """25 answers should be processed in 2 batches (20+5), all succeed."""
    import asyncio

    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ctx = {"db_session_factory": sf}

    peak_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def mock_grade_fn(*args, **kwargs):
        nonlocal peak_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            peak_concurrent = max(peak_concurrent, current_concurrent)
        await asyncio.sleep(0.01)  # simulate LLM latency
        async with lock:
            current_concurrent -= 1
        return GradeResponse(score=9.0, max_score=10.0, feedback="good", confidence=0.95)

    mock_client = AsyncMock()
    mock_client.grade = AsyncMock(side_effect=mock_grade_fn)
    mock_client.close = AsyncMock()

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="fakebase64"):
        with patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_client):
            await process_grading_task(ctx, grading_setup_25["task_id"])

    async with sf() as session:
        result = await session.execute(
            select(GradingTask).where(GradingTask.id == grading_setup_25["task_id"])
        )
        task = result.scalar_one()
        assert task.status == "completed"
        assert task.completed == 25
        assert task.failed == 0

        results = await session.execute(
            select(GradingResult).where(GradingResult.ai_task_id == task.id)
        )
        assert len(results.scalars().all()) == 25

    # Peak concurrency should be > 1 (proves batching, not serial)
    assert peak_concurrent > 1, f"Expected concurrent execution but peak was {peak_concurrent}"


async def test_batch_partial_failure_in_batch(db_engine, db, grading_setup_25):
    """Some answers fail within a batch — failures recorded, rest succeed."""
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ctx = {"db_session_factory": sf}

    call_count = 0

    async def mock_grade_fn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail every 5th call
        if call_count % 5 == 0:
            raise RuntimeError("LLM error")
        return GradeResponse(score=8.0, max_score=10.0, feedback="ok", confidence=0.85)

    mock_client = AsyncMock()
    mock_client.grade = AsyncMock(side_effect=mock_grade_fn)
    mock_client.close = AsyncMock()

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="fakebase64"):
        with patch("edu_cloud.workers.grading._create_llm_client", return_value=mock_client):
            await process_grading_task(ctx, grading_setup_25["task_id"])

    async with sf() as session:
        result = await session.execute(
            select(GradingTask).where(GradingTask.id == grading_setup_25["task_id"])
        )
        task = result.scalar_one()
        # 5 failures (calls 5,10,15,20,25)
        assert task.failed == 5
        assert task.completed == 20
        assert task.status == "failed"
        assert len(task.error_log) == 5
