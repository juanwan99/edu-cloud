"""WorkflowEngine tests — registry + executor with idempotency and retry."""
import pytest
from datetime import date

from edu_cloud.ai.workflow.registry import (
    StepDefinition,
    WorkflowDefinition,
    WorkflowRegistry,
)
from edu_cloud.ai.workflow.engine import WorkflowContext, WorkflowExecutor
from edu_cloud.models.workflow import WorkflowRun, WorkflowStep
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Registry tests (sync, no DB needed)
# ---------------------------------------------------------------------------

def test_register_and_get_workflow():
    """Registry stores and retrieves workflows."""
    registry = WorkflowRegistry()

    async def step_a(ctx: WorkflowContext) -> dict:
        return {"ok": True}

    wf = WorkflowDefinition(
        name="test_wf",
        steps=[StepDefinition(name="step_a", func=step_a)],
    )
    registry.register(wf)
    assert registry.get("test_wf") is wf
    assert "test_wf" in registry.list_all()


def test_registry_rejects_duplicate():
    """Duplicate name raises ValueError."""
    registry = WorkflowRegistry()

    async def noop(ctx: WorkflowContext) -> None:
        pass

    wf = WorkflowDefinition(name="dup", steps=[StepDefinition(name="s", func=noop)])
    registry.register(wf)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(wf)


def test_registry_get_missing_returns_none():
    """Getting unregistered workflow returns None."""
    registry = WorkflowRegistry()
    assert registry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Executor tests (async, need DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_executor_runs_all_steps(db):
    """All steps run in order, outputs captured."""
    call_order = []

    async def step_one(ctx: WorkflowContext) -> dict:
        call_order.append("one")
        return {"val": 1}

    async def step_two(ctx: WorkflowContext) -> dict:
        call_order.append("two")
        # Verify step_one output is available
        assert ctx.step_outputs["step_one"] == {"val": 1}
        return {"val": 2}

    wf = WorkflowDefinition(
        name="two_step",
        steps=[
            StepDefinition(name="step_one", func=step_one),
            StepDefinition(name="step_two", func=step_two),
        ],
    )

    executor = WorkflowExecutor(db)
    run = await executor.execute(wf, school_id="s1", trigger_type="manual", trigger_ref="ref1")

    assert call_order == ["one", "two"]
    assert run.status == "completed"
    assert run.current_step == 2
    assert run.total_steps == 2
    assert run.completed_at is not None

    # Verify step records
    result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id).order_by(WorkflowStep.step_index)
    )
    steps = result.scalars().all()
    assert len(steps) == 2
    assert steps[0].step_name == "step_one"
    assert steps[0].status == "completed"
    assert steps[0].output_summary == {"val": 1}
    assert steps[1].step_name == "step_two"
    assert steps[1].status == "completed"
    assert steps[1].output_summary == {"val": 2}


@pytest.mark.asyncio
async def test_executor_idempotency_skips_duplicate(db):
    """Same trigger_ref same day -> second call skips."""
    call_count = 0

    async def counting_step(ctx: WorkflowContext) -> dict:
        nonlocal call_count
        call_count += 1
        return {}

    wf = WorkflowDefinition(
        name="idempotent_wf",
        steps=[StepDefinition(name="s", func=counting_step)],
    )

    executor = WorkflowExecutor(db)
    run1 = await executor.execute(wf, school_id="s1", trigger_type="manual", trigger_ref="same_ref")
    run2 = await executor.execute(wf, school_id="s1", trigger_type="manual", trigger_ref="same_ref")

    assert call_count == 1  # step only ran once
    assert run1.id == run2.id  # same run returned
    assert run2.status == "completed"


@pytest.mark.asyncio
async def test_executor_retries_on_failure(db):
    """Transient failures retried, succeeds on 3rd attempt."""
    attempt = 0

    async def flaky_step(ctx: WorkflowContext) -> dict:
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise RuntimeError("transient error")
        return {"survived": True}

    wf = WorkflowDefinition(
        name="retry_wf",
        steps=[StepDefinition(name="flaky", func=flaky_step)],
        max_retries=3,
    )

    executor = WorkflowExecutor(db)
    run = await executor.execute(wf, school_id="s1", trigger_type="auto", trigger_ref="retry_ref")

    assert run.status == "completed"
    assert run.retry_count == 2  # 2 retries before success on 3rd attempt

    result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id)
    )
    step = result.scalars().first()
    assert step.status == "completed"
    assert step.output_summary == {"survived": True}


@pytest.mark.asyncio
async def test_executor_fails_after_max_retries(db):
    """Permanent failures exhaust retries -> status=failed."""

    async def always_fail(ctx: WorkflowContext) -> dict:
        raise RuntimeError("permanent error")

    wf = WorkflowDefinition(
        name="fail_wf",
        steps=[StepDefinition(name="bad_step", func=always_fail)],
        max_retries=2,
    )

    executor = WorkflowExecutor(db)
    run = await executor.execute(wf, school_id="s1", trigger_type="auto", trigger_ref="fail_ref")

    assert run.status == "failed"
    assert "permanent error" in run.last_error
    assert run.retry_count == 2
    assert run.completed_at is None

    result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id)
    )
    step = result.scalars().first()
    assert step.status == "failed"
    assert "permanent error" in step.error


@pytest.mark.asyncio
async def test_executor_step_returning_none(db):
    """Steps returning None are recorded with empty dict output."""

    async def void_step(ctx: WorkflowContext) -> None:
        pass

    wf = WorkflowDefinition(
        name="void_wf",
        steps=[StepDefinition(name="void", func=void_step)],
    )

    executor = WorkflowExecutor(db)
    run = await executor.execute(wf, school_id="s1", trigger_type="manual", trigger_ref="void_ref")

    assert run.status == "completed"

    result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.run_id == run.id)
    )
    step = result.scalars().first()
    assert step.output_summary == {}
