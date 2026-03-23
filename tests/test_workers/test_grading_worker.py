"""Grading worker tests — mock Redis, verify task registration."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


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
