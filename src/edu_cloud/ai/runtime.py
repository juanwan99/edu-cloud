"""AgentRuntime: transport-agnostic Agent execution."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.capability_probe import CapabilityProbe, LoopStrategy
from edu_cloud.ai.grounded import OutputValidator
from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import tools as tool_registry
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.agent_team import teams as default_team_registry
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentContext:
    """All context for one Agent invocation."""
    db: AsyncSession
    user_id: str
    school_id: str
    role: str
    data_scope: Any
    session_id: str
    user_slots: list[Any] = field(default_factory=list)
    system_slots: list[Any] = field(default_factory=list)
    enhanced_enabled: bool = False
    class_ids: list[str] | None = None
    subject_codes: list[str] | None = None
    capabilities: dict[tuple[str, str], bool] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    display_name: str = ""
    school_name: str = ""
    anonymizer: Any | None = None  # F004 fix


SCHEDULED_PROMPTS: dict[str, str] = {
    "daily_grade_alert": "检查今天是否有异常成绩数据，如有则生成预警摘要。",
    "weekly_class_report": "生成本周各班级的成绩变化摘要报告。",
    "exam_analysis": "对刚发布的考试进行全面分析：成绩分布、薄弱知识点、班级对比。",
}


class AgentRuntime:
    """Stateless Agent runtime. Each run() is independent."""

    def __init__(self):
        self._model_router = ModelRouter()
        self._memory_store = MemoryStore()
        self._memory_injector = MemoryInjector(store=self._memory_store)
        self._memory_extractor = MemoryExtractor(store=self._memory_store)
        self._validator = OutputValidator()
        self._probe = CapabilityProbe()
        self._tool_resolver = ToolAccessResolver()
        self._last_history: list | None = None
        self._last_run_info: dict | None = None

    async def run(
        self,
        message: str,
        context: AgentContext,
        history: list | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute Agent pipeline. Yields AgentEvent stream."""
        from edu_cloud.config import settings

        # 1. Model routing (F002 fix: use llm-proxy, not slot.api_url)
        slot_name = "ai-chat"
        try:
            model_choice = self._model_router.route(
                message, context.user_slots, context.system_slots,
                enhanced_enabled=context.enhanced_enabled,
            )
            if model_choice.tier == "advanced" and context.system_slots:
                slot_name = "ai-enhanced"
        except ValueError:
            # No slots configured (e.g. test env) — fall back to default slot
            logger.debug("ModelRouter: no slots configured, using default slot %s", slot_name)
        adapter = LLMProxyAdapter(
            base_url=settings.LLM_API_URL or "http://localhost:8100",
            slot=slot_name,
        )

        # 2. Capability probe
        tier = await self._probe.determine_tier(adapter)
        strategy = LoopStrategy.for_tier(tier)

        # 3. Memory injection (Tier 1-2)
        memory_context = ""
        if tier <= 2:
            try:
                memory_context = await self._memory_injector.build_context(
                    db=context.db, school_id=context.school_id,
                    user_id=context.user_id, role=context.role,
                    class_ids=context.class_ids,
                    student_ids=(context.data_scope.visible_student_ids
                                 if context.data_scope else None),
                )
            except Exception:
                logger.exception("Memory injection failed (non-blocking)")

        # 4. Tool resolution
        available_tools = self._tool_resolver.resolve(
            tool_registry.get_all_specs(),
            role=context.role,
            enabled_modules=context.enabled_modules,
            capabilities=context.capabilities,
        )

        # 5. Build prompt
        from edu_cloud.ai.prompts import build_teacher_prompt
        tool_names = [t.name for t in available_tools]
        system_prompt = build_teacher_prompt(
            role=context.role,
            display_name=context.display_name,
            school_name=context.school_name,
            tool_names=tool_names,
            tier=tier,
        ) + memory_context

        # 6. Build ToolContext (F004 fix: preserve anonymizer)
        tool_ctx = ToolContext(
            db=context.db,
            school_id=context.school_id,
            user_id=context.user_id,
            role=context.role,
            class_ids=context.class_ids,
            subject_codes=context.subject_codes,
            capabilities=context.capabilities,
            enabled_modules=context.enabled_modules,
            data_scope=context.data_scope,
            anonymizer=context.anonymizer,
        )

        # 7. Supervisor — teams disabled: single loop handles all queries
        #    (team routing adds latency + unreliable sub-agent execution)
        mem_extractor = self._memory_extractor if strategy.tier == 1 else None
        sensitivity_router = SensitivityRouter(primary=adapter, enhanced=None)
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=adapter,
            strategy=strategy,
            team_registry=None,
            sensitivity_router=sensitivity_router,
            memory_extractor=mem_extractor,
        )

        # 8. Execute and yield events
        from edu_cloud.ai.tool_context import ToolResult
        collected_tool_results: list[ToolResult] = []
        try:
            async for event in supervisor.handle(
                message=message,
                ctx=tool_ctx,
                tool_specs=available_tools,
                system_prompt=system_prompt,
                history=history,
                session_id=context.session_id,
            ):
                # F001: collect tool_result data for OutputValidator
                # agent_loop emits {"tool": ..., "result": ...} — read "result" key
                # with fallback to "data" for forward compat
                if event.type == "tool_result" and isinstance(event.data, dict):
                    payload = event.data.get("result", event.data.get("data"))
                    if payload is not None and not (
                        isinstance(payload, dict) and "error" in payload
                    ):
                        collected_tool_results.append(
                            ToolResult(success=True, data=payload)
                        )

                # F001: validate answer events against collected tool data
                if event.type == "answer":
                    content = (
                        event.data.get("content", "")
                        if isinstance(event.data, dict)
                        else ""
                    )
                    if content and collected_tool_results:
                        vr = self._validator.validate(content, collected_tool_results)
                        if vr.status == "fail":
                            logger.warning(
                                "OutputValidator FAIL: contradictions=%s", vr.contradictions
                            )
                        elif vr.status == "warn":
                            logger.warning(
                                "OutputValidator WARN: ungrounded=%s", vr.ungrounded_values
                            )

                yield event
        finally:
            # F005: always close the adapter
            await adapter.close()
            # F002: save history for api/ai.py to write back
            self._last_history = supervisor.get_history()
            # F004: save execution receipt with real values
            self._last_run_info = {
                "tools_resolved": [t.name for t in available_tools],
                "model_used": slot_name,
                "model_tier": supervisor.model_tier,
            }

    def get_last_history(self) -> list | None:
        """Return the supervisor's history from the most recent run (F002)."""
        return self._last_history

    def get_last_run_info(self) -> dict | None:
        """Return execution receipt from the most recent run (F004)."""
        return self._last_run_info
