"""AgentDeps — the dependency container injected into every tool via RunContext."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from edu_cloud.ai.anonymizer import Anonymizer
    from edu_cloud.ai.data_scope import DataScope
    from edu_cloud.ai.engine.artifact_manager import ArtifactManager
    from edu_cloud.ai.engine.budget import AgentBudget
    from edu_cloud.ai.engine.confirmation_broker import ConfirmationBroker
    from edu_cloud.ai.engine.policy_guardrail import PolicyToolGuardrail
    from edu_cloud.ai.engine.trace_recorder import TraceRecorder
    from edu_cloud.ai.memory_store import MemoryStore


@dataclass(slots=True)
class AgentDeps:
    """Passed as deps_type to pydantic_ai.Agent.

    Every field is populated once at request start and remains stable
    for the lifetime of the agent run. Mutable state (budget counters,
    trace events) is managed internally by the owning objects.
    """

    # ── Identity ──
    run_id: str
    request_id: str
    session_id: str
    user_id: str
    school_id: str
    role: str

    # ── Permissions (immutable for the run) ──
    data_scope: DataScope
    enabled_modules: frozenset[str]
    capabilities: Mapping[tuple[str, str], bool]

    # ── Infrastructure ──
    db_sessionmaker: async_sessionmaker[AsyncSession]
    budget: AgentBudget
    policy: PolicyToolGuardrail
    confirmations: ConfirmationBroker
    artifacts: ArtifactManager
    trace: TraceRecorder
    memory: MemoryStore
    anonymizer: Anonymizer

    # ── Model routing ──
    model_slot: str = "ai-chat"

    # ── Event stream (set by runtime before run, drained by SSE handler) ──
    event_queue: asyncio.Queue | None = field(default=None, repr=False)

    def get_db(self) -> Any:
        """Create an independent AsyncSession for a tool.

        Usage in tools:
            async with ctx.deps.get_db() as db:
                result = await db.execute(...)
        """
        return self.db_sessionmaker()
