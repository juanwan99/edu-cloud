"""Grading worker tests — mock Redis, verify task registration and grading flow."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import async_sessionmaker


def test_worker_settings_has_grading_functions():
    """WorkerSettings registers grading + pipeline functions."""
    from edu_cloud.worker import WorkerSettings
    func_names = [f.__name__ if hasattr(f, "__name__") else str(f) for f in WorkerSettings.functions]
    assert "process_grading_task" in func_names
    assert "run_post_exam_pipeline" in func_names
    assert "run_auto_draft" in func_names


def test_worker_settings_has_cron_jobs():
    """WorkerSettings has at least 1 cron job."""
    from edu_cloud.worker import WorkerSettings
    assert len(WorkerSettings.cron_jobs) >= 1


@pytest.mark.asyncio
async def test_run_post_exam_pipeline_stub():
    """Pipeline stub runs without error."""
    from edu_cloud.workers.grading import run_post_exam_pipeline
    ctx = {}
    await run_post_exam_pipeline(ctx, exam_id="test-exam", school_id="test-school")


def test_process_grading_task_is_importable():
    """process_grading_task can be imported and has correct signature."""
    from edu_cloud.workers.grading import process_grading_task
    import inspect
    sig = inspect.signature(process_grading_task)
    assert "ctx" in sig.parameters
    assert "task_id" in sig.parameters


def test_run_post_exam_pipeline_is_importable():
    """run_post_exam_pipeline can be imported and has correct signature."""
    from edu_cloud.workers.grading import run_post_exam_pipeline
    import inspect
    sig = inspect.signature(run_post_exam_pipeline)
    assert "ctx" in sig.parameters
    assert "exam_id" in sig.parameters
    assert "school_id" in sig.parameters


# ── Flow tests ─────────────────────────────────────────────────────


def _make_mock_task(task_id="task-1", subject_id="subj-1", school_id="school-1",
                    question_id=None):
    """Create a mock GradingTask with writable attributes."""
    task = MagicMock()
    task.id = task_id
    task.subject_id = subject_id
    task.school_id = school_id
    task.question_id = question_id  # None = subject-level; str = question-level
    task.status = "pending"
    task.total = 0
    task.completed = 0
    task.failed = 0
    task.grading_limit = None
    task.grading_mode = "realtime"
    task.error_log = None
    return task


def _make_scalar_one_result(obj):
    """Wrap an object so result.scalar_one() returns it."""
    result = MagicMock()
    result.scalar_one.return_value = obj
    return result


def _make_scalars_all_result(items):
    """Wrap a list so result.scalars().all() returns it."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result.scalars.return_value = scalars_mock
    return result


def _build_mock_db_session(execute_side_effects):
    """Build a mock async session factory + session from a list of execute return values.

    Returns (ctx_dict, db_mock) where ctx_dict has 'db_session_factory'.
    """
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_side_effects)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()

    # session_factory() returns an async context manager yielding db
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    session_factory = MagicMock(spec=async_sessionmaker)
    session_factory.return_value = session_cm

    ctx = {"db_session_factory": session_factory}
    return ctx, db


@pytest.mark.asyncio
@patch("edu_cloud.modules.exam.slot_selector.get_llm_config", new_callable=AsyncMock, side_effect=Exception("no slot"))
@patch("edu_cloud.workers.grading._create_llm_client")
async def test_process_grading_task_no_subjective_questions(mock_create_llm, _mock_get_cfg):
    """No subjective questions → task completes immediately without LLM calls."""
    from edu_cloud.workers.grading import process_grading_task

    task = _make_mock_task()
    task.status = "processing"  # post-CAS state: worker code re-reads after claim

    # db.execute call sequence (CAS task claim):
    # 1. update(GradingTask) WHERE status=pending → rowcount=1 (CAS claim)
    # 2. select(GradingTask) → task (re-read after claim, status=processing)
    # 3. select(Question) → empty list
    # 4. select(Subject) → None (subject lookup for prompt dispatch)
    cas_result = MagicMock()
    cas_result.rowcount = 1
    subject_result = MagicMock()
    subject_result.scalar_one_or_none.return_value = None
    execute_results = [
        cas_result,                      # CAS claim: pending → processing
        _make_scalar_one_result(task),   # re-read GradingTask after claim
        _make_scalars_all_result([]),     # no subjective questions
        subject_result,                  # subject lookup
    ]
    ctx, db = _build_mock_db_session(execute_results)

    mock_llm = AsyncMock()
    mock_create_llm.return_value = mock_llm

    await process_grading_task(ctx, "task-1")

    # Task should transition: processing → completed
    assert task.status == "completed"
    # LLM grade should never be called
    mock_llm.grade.assert_not_called()
    # LLM client should be closed
    mock_llm.close.assert_awaited_once()
    # DB commit called at least twice (claim + completed)
    assert db.commit.await_count >= 2


@pytest.mark.asyncio
@patch("edu_cloud.modules.exam.slot_selector.get_llm_config", new_callable=AsyncMock, side_effect=Exception("no slot"))
@patch("edu_cloud.workers.grading._create_llm_client")
async def test_process_grading_task_missing_rubric(mock_create_llm, _mock_get_cfg):
    """Answer exists but no rubric for question → task.failed incremented."""
    from edu_cloud.workers.grading import process_grading_task

    task = _make_mock_task()
    task.status = "processing"  # post-CAS state: worker code re-reads after claim

    question = MagicMock()
    question.id = "q-1"
    question.name = "Essay Q1"
    question.max_score = 10.0
    question.subject_id = "subj-1"
    question.school_id = "school-1"
    question.question_type = "essay"

    answer = MagicMock()
    answer.id = "ans-1"
    answer.question_id = "q-1"
    answer.image_path = "/fake/path.png"
    answer.subject_id = "subj-1"
    answer.school_id = "school-1"

    # db.execute call sequence (CAS task claim + batch mode):
    # 1. update(GradingTask) WHERE status=pending → rowcount=1 (CAS claim)
    # 2. select(GradingTask) → task (re-read after claim, status=processing)
    # 3. select(Question) → [question]
    # 4. select(Subject) → None (subject lookup for prompt dispatch)
    # 5. select(StudentAnswer) → [answer]
    # 6. select(GradingResult.answer_id) WHERE confirmed → [] (ORC-001 exclusion)
    # 7. select(Rubric) → [] (no rubric!)
    # 8. select(GradingTask) → task (batch progress re-fetch)
    # 9. select(GradingTask) → task (final status re-fetch)
    cas_result = MagicMock()
    cas_result.rowcount = 1
    subject_result = MagicMock()
    subject_result.scalar_one_or_none.return_value = None
    execute_results = [
        cas_result,                          # CAS claim: pending → processing
        _make_scalar_one_result(task),       # re-read GradingTask after claim
        _make_scalars_all_result([question]), # subjective questions
        subject_result,                      # subject lookup
        _make_scalars_all_result([answer]),   # student answers
        _make_scalars_all_result([]),         # confirmed exclusion (ORC-001) → none
        _make_scalars_all_result([]),         # no rubrics
        _make_scalar_one_result(task),        # batch progress re-fetch
        _make_scalar_one_result(task),        # final status re-fetch
    ]
    ctx, db = _build_mock_db_session(execute_results)

    mock_llm = AsyncMock()
    mock_create_llm.return_value = mock_llm

    await process_grading_task(ctx, "task-1")

    # failed should be incremented (no rubric for q-1)
    assert task.failed >= 1
    # LLM grade should never be called (skipped due to missing rubric)
    mock_llm.grade.assert_not_called()
    # Final status is "failed" because errors list is non-empty
    assert task.status == "failed"
    assert task.error_log is not None
    mock_llm.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_grading_task_llm_recoverable_error():
    """LLM extract_text raises ValueError → error caught, result contains error."""
    from edu_cloud.workers.grading import _grade_single

    mock_llm = MagicMock()
    mock_llm.extract_text = AsyncMock(side_effect=ValueError("LLM parse error"))
    mock_llm.model = "test-model"

    ad = {
        "answer_id": "ans-1", "question_id": "q-1",
        "question_name": "Essay Q1", "question_max_score": 10,
        "image_path": "/tmp/fake.png", "question_type": "essay",
        "subject_code": "biology",
    }
    rubrics = {"q-1": [{"blankNo": "1-1", "score": 10, "standardAnswer": "X", "context": "ctx", "judgingRules": "rules"}]}

    with patch("edu_cloud.workers.grading._read_image_b64", new_callable=AsyncMock, return_value="A" * 10000):
        result, error, plog = await _grade_single(mock_llm, ad, rubrics)

    mock_llm.extract_text.assert_awaited_once()
    assert result is None
    assert error is not None
    assert "LLM parse error" in error["error"]
    assert plog["error_type"] == "ValueError"
