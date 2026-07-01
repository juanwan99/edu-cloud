"""Workflow executor — runs workflow steps with persistent state, idempotency, and retry."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.workflow.registry import WorkflowDefinition
from edu_cloud.models.workflow import WorkflowRun, WorkflowStep

logger = logging.getLogger(__name__)


class WorkflowContext:
    """Passed to each step function."""

    def __init__(
        self,
        db: AsyncSession,
        school_id: str,
        trigger_ref: str,
        run_id: str,
        step_outputs: dict[str, dict],
    ) -> None:
        self.db = db
        self.school_id = school_id
        self.trigger_ref = trigger_ref
        self.run_id = run_id
        self.step_outputs = step_outputs


class WorkflowExecutor:
    """Execute a workflow definition against the database with idempotency and retry."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(
        self,
        workflow: WorkflowDefinition,
        school_id: str,
        trigger_type: str,
        trigger_ref: str,
    ) -> WorkflowRun:
        idempotency_key = f"{school_id}:{workflow.name}:{trigger_ref}:{date.today()}"

        # Check for existing run with same idempotency key
        result = await self._db.execute(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        existing = result.scalars().first()

        if existing and existing.status in ("completed", "running"):
            return existing

        # Create or reuse run record
        if existing:
            run = existing
        else:
            run = WorkflowRun(
                school_id=school_id,
                workflow_name=workflow.name,
                trigger_type=trigger_type,
                trigger_ref=trigger_ref,
                idempotency_key=idempotency_key,
                status="running",
                current_step=0,
                total_steps=len(workflow.steps),
                retry_count=0,
            )
            try:
                self._db.add(run)
                await self._db.flush()
            except IntegrityError:
                await self._db.rollback()
                # Re-query the existing run (concurrent insert)
                existing = (await self._db.execute(
                    select(WorkflowRun).where(
                        WorkflowRun.idempotency_key == idempotency_key
                    )
                )).scalar_one()
                if existing.status in ("completed", "running"):
                    return existing
                run = existing

        run.status = "running"

        # Collect outputs from already-completed steps
        step_outputs: dict[str, dict] = {}
        if run.current_step > 0:
            completed_result = await self._db.execute(
                select(WorkflowStep)
                .where(
                    WorkflowStep.run_id == run.id,
                    WorkflowStep.status == "completed",
                )
                .order_by(WorkflowStep.step_index)
            )
            for ws in completed_result.scalars().all():
                step_outputs[ws.step_name] = ws.output_summary or {}

        # Execute steps starting from current_step
        for i in range(run.current_step, len(workflow.steps)):
            step_def = workflow.steps[i]
            ctx = WorkflowContext(
                db=self._db,
                school_id=school_id,
                trigger_ref=trigger_ref,
                run_id=run.id,
                step_outputs=step_outputs,
            )

            step_record = WorkflowStep(
                run_id=run.id,
                step_index=i,
                step_name=step_def.name,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            self._db.add(step_record)
            await self._db.flush()

            # Try with retries
            max_attempts = workflow.max_retries + 1
            success = False
            last_error: str | None = None

            for attempt in range(max_attempts):
                try:
                    output = await step_def.func(ctx)
                    output = output if output is not None else {}

                    step_record.status = "completed"
                    step_record.output_summary = output
                    step_record.completed_at = datetime.now(timezone.utc)

                    step_outputs[step_def.name] = output
                    run.current_step = i + 1
                    success = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < max_attempts - 1:
                        run.retry_count += 1
                        logger.warning(
                            "Step %s attempt %d failed: %s",
                            step_def.name,
                            attempt + 1,
                            last_error,
                        )

            if not success:
                step_record.status = "failed"
                step_record.error = last_error
                await self._record_skipped_steps(
                    run_id=run.id,
                    workflow=workflow,
                    failed_step_index=i,
                    failed_step_name=step_def.name,
                )
                run.status = "failed"
                run.last_error = last_error
                await self._db.commit()
                return run

        # All steps completed
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await self._db.commit()
        return run

    async def _record_skipped_steps(
        self,
        *,
        run_id: str,
        workflow: WorkflowDefinition,
        failed_step_index: int,
        failed_step_name: str,
    ) -> None:
        skip_reason = f"skipped because upstream step failed: {failed_step_name}"
        for skipped_index in range(failed_step_index + 1, len(workflow.steps)):
            skipped_def = workflow.steps[skipped_index]
            self._db.add(WorkflowStep(
                run_id=run_id,
                step_index=skipped_index,
                step_name=skipped_def.name,
                status="skipped",
                error=skip_reason,
            ))
        await self._db.flush()
