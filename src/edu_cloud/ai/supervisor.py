# src/edu_cloud/ai/supervisor.py
"""Supervisor: routes requests to single AgentLoop or AgentTeam."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from typing import TYPE_CHECKING

from edu_cloud.ai.agent_loop import AgentLoop
from edu_cloud.ai.agent_spec import select_slot
from edu_cloud.ai.agent_team import AgentTeam, TeamExecutor, TeamRegistry
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.tool_context import ToolContext

if TYPE_CHECKING:
    from edu_cloud.ai.memory_extractor import MemoryExtractor

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    needs_team: bool
    team_name: str | None = None
    reason: str = ""


class Supervisor:
    """Routes user requests to single AgentLoop or multi-agent team."""

    def __init__(
        self,
        registry: ToolRegistry,
        adapter: LLMProxyAdapter,
        strategy: LoopStrategy,
        team_registry: TeamRegistry | None = None,
        sensitivity_router: SensitivityRouter | None = None,
        memory_extractor: "MemoryExtractor | None" = None,
    ):
        self._registry = registry
        self._adapter = adapter
        self._strategy = strategy
        self._team_registry = team_registry
        self._sensitivity_router = sensitivity_router
        self._memory_extractor = memory_extractor
        self._team_executor = TeamExecutor()
        # Execution receipt — stable public interface (F002 fix)
        self._history: list[Message] = []
        self._model_tier: str = f"tier{strategy.tier}"
        self._dispatched_team: str | None = None

    def get_history(self) -> list[Message]:
        """Return conversation history from last run (stable public API)."""
        return self._history

    @property
    def model_tier(self) -> str:
        """Return model tier as string (e.g. 'tier1'), matching record_run contract."""
        return self._model_tier

    @property
    def dispatched_team(self) -> str | None:
        """Return name of dispatched team, or None if single loop was used."""
        return self._dispatched_team

    async def handle(
        self,
        message: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        history: list[Message] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Main entry point. Yields AgentEvents (compatible with SSE stream)."""

        # If no teams registered or tier 3, always use single loop
        if not self._team_registry or self._strategy.tier == 3:
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            await self._maybe_extract_memory(ctx, session_id)
            return

        # Classify intent
        classification = await self._classify(message, tool_specs)

        if not classification.needs_team:
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            await self._maybe_extract_memory(ctx, session_id)
            return

        # Try to get the team
        team = self._team_registry.get(classification.team_name) if classification.team_name else None
        if team is None:
            logger.warning(
                "Classified as team '%s' but team not found, falling back to single loop",
                classification.team_name,
            )
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            await self._maybe_extract_memory(ctx, session_id)
            return

        # Dispatch to team
        yield AgentEvent(type="status", data={"message": f"正在调度 {team.name} 团队..."})

        try:
            team_result = await self._run_team(team, message, ctx, system_prompt=system_prompt, allowed_tools=tool_specs)
            self._dispatched_team = team.name
        except Exception:
            logger.exception("Team '%s' execution failed, falling back", team.name)
            async for event in self._run_single(
                message, ctx, tool_specs=tool_specs,
                system_prompt=system_prompt, history=history,
            ):
                yield event
            await self._maybe_extract_memory(ctx, session_id)
            return

        # Summarize team results via LLM
        summary = await self._summarize(message, team_result)
        # F002 fix: preserve multi-turn history
        prior_history = list(history) if history else []
        self._history = prior_history + [
            Message(role="user", content=message),
            Message(role="assistant", content=summary),
        ]
        yield AgentEvent(type="answer", data={"content": summary})
        yield AgentEvent(type="done", data={})
        await self._maybe_extract_memory(ctx, session_id)

    async def _maybe_extract_memory(self, ctx: ToolContext, session_id: str | None) -> None:
        """Post-run: extract and persist memory (Tier 1 only, non-blocking)."""
        if (
            self._memory_extractor
            and self._strategy.tier == 1
            and session_id
        ):
            try:
                await self._memory_extractor.extract_and_persist(
                    db=ctx.db,
                    messages=self._history,
                    adapter=self._adapter,
                    school_id=ctx.school_id,
                    user_id=ctx.user_id,
                    session_id=session_id,
                )
            except Exception:
                logger.exception("Memory extraction failed (non-blocking)")

    async def _classify(
        self,
        message: str,
        tool_specs: list[ToolSpec],
    ) -> ClassificationResult:
        """Use LLM to classify whether this request needs a team."""
        if not self._team_registry:
            return ClassificationResult(needs_team=False)

        team_descs = self._team_registry.get_descriptions()
        teams_text = "\n".join(f"- {t['name']}: {t['description']}" for t in team_descs)

        prompt = (
            "你是请求分类器。判断用户请求是简单还是复杂。\n"
            "简单请求：单个工具就能完成（查询、问答、单步操作）。\n"
            "复杂请求：需要多个步骤协作完成（分析+报告、多维对比、批量处理）。\n\n"
            f"可用团队：\n{teams_text}\n\n"
            '简单请求回复：{{"needs_team": false}}\n'
            '复杂请求回复：{{"needs_team": true, "team_name": "团队名"}}\n'
            "只回复 JSON，不要其他内容。"
        )

        try:
            resp = await self._adapter.chat(LLMRequest(
                messages=[
                    Message(role="system", content=prompt),
                    Message(role="user", content=message),
                ],
                max_tokens=200,
                stream=False,
            ))
            data = json.loads(resp.content)
            return ClassificationResult(
                needs_team=data.get("needs_team", False),
                team_name=data.get("team_name"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, Exception) as exc:
            logger.warning("Classification failed: %s, defaulting to simple", exc)
            return ClassificationResult(needs_team=False)

    async def _run_single(
        self,
        message: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        history: list[Message] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Delegate to existing single AgentLoop (backward compatible)."""
        loop = AgentLoop(
            registry=self._registry,
            adapter=self._adapter,
            strategy=self._strategy,
            sensitivity_router=self._sensitivity_router,
        )
        async for event in loop.run(
            goal=message,
            ctx=ctx,
            tool_specs=tool_specs,
            system_prompt=system_prompt,
            history=history,
        ):
            yield event
        # Capture history for multi-turn persistence
        self._history = loop.get_history()
        self._dispatched_team = None

    async def _run_team(
        self,
        team: AgentTeam,
        goal: str,
        ctx: ToolContext,
        system_prompt: str = "",
        allowed_tools: list[ToolSpec] | None = None,
    ) -> str:
        """Execute team via TeamExecutor, wiring sub-agents to AgentLoop."""
        state = SharedState()
        state.set("goal", goal)

        # F001 fix: build allowed tool name set from ToolAccessResolver output
        allowed_names = {t.name for t in allowed_tools} if allowed_tools is not None else None

        original_run = self._team_executor._run_sub_agent

        async def wired_run(spec, goal, state, **kwargs):
            # F001 fix: intersect spec.tools with allowed tools
            if allowed_names is not None:
                from edu_cloud.ai.agent_spec import AgentSpec
                filtered_tool_names = [t for t in spec.tools if t in allowed_names]
                spec = AgentSpec(
                    name=spec.name, description=spec.description,
                    tools=filtered_tool_names, model_tier=spec.model_tier,
                    max_turns=spec.max_turns, task_complexity=spec.task_complexity,
                )

            slot = select_slot(spec)
            sub_adapter = LLMProxyAdapter(
                base_url=self._adapter._base_url,
                slot=slot,
                context_window=self._adapter._context_window,
            )
            try:
                sub_loop = AgentLoop(
                    registry=self._registry,
                    adapter=sub_adapter,
                    strategy=LoopStrategy.for_tier(spec.model_tier or self._strategy.tier),
                )
                return await sub_loop.run_as_sub_agent(
                    spec=spec, goal=goal, ctx=ctx, state=state,
                    system_prompt=system_prompt,
                )
            finally:
                await sub_adapter.close()

        self._team_executor._run_sub_agent = wired_run
        try:
            results = await self._team_executor.run(team, goal, state)
        finally:
            self._team_executor._run_sub_agent = original_run

        return "\n\n".join(results)

    async def _summarize(self, original_question: str, team_output: str) -> str:
        """Use LLM to synthesize team results into a coherent response."""
        if not team_output.strip():
            return "抱歉，团队执行没有产生有效结果。"

        try:
            resp = await self._adapter.chat(LLMRequest(
                messages=[
                    Message(
                        role="system",
                        content=(
                            "你是结果汇总器。根据多个 Agent 的执行结果，"
                            "生成一个连贯、完整的回答给用户。保持原始数据的准确性。"
                        ),
                    ),
                    Message(
                        role="user",
                        content=f"用户问题：{original_question}\n\nAgent 执行结果：\n{team_output}",
                    ),
                ],
                max_tokens=2000,
                stream=False,
            ))
            return resp.content or team_output
        except Exception:
            logger.exception("Summarization failed, returning raw results")
            return team_output
