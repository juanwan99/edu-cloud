"""Core agent loop — plan, execute tools, verify, respond (Design §3).

Implements the full state machine: CapabilityProbe → SensitivityRouter →
plan branch (tier ≤ 2) → tool execution → thinking/plan/task_update events →
error threshold → memory extract.

Inspired by Claude Code's query.ts AsyncGenerator pattern.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.context_manager import ContextManager, TokenCounter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest, LLMResponse
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message, ToolCall, Transition
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.session_memory import SessionMemoryExtractor
from edu_cloud.ai.task_planner import TaskPlanner
from edu_cloud.ai.tool_context import ToolContext
from edu_cloud.ai.tool_executor import ToolOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    messages: list[Message]
    turn_count: int = 0
    token_count: int = 0
    error_count: int = 0
    channel: str = "primary"


class AgentLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        adapter: LLMProxyAdapter,
        strategy: LoopStrategy,
        sensitivity_router: SensitivityRouter | None = None,
        memory_extractor: SessionMemoryExtractor | None = None,
    ):
        self._registry = registry
        self._adapter = adapter
        self._strategy = strategy
        self._orchestrator = ToolOrchestrator(registry)
        self._context_mgr = ContextManager()
        self._planner = TaskPlanner()
        self._sensitivity_router = sensitivity_router
        self._memory_extractor = memory_extractor

    async def run(
        self,
        goal: str,
        ctx: ToolContext,
        *,
        tool_specs: list[ToolSpec],
        system_prompt: str = "",
        memories: list[str] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        state = AgentState(messages=[])

        # Build initial messages
        if system_prompt:
            state.messages.append(Message(role="system", content=system_prompt))
        state.messages.append(Message(role="user", content=goal))
        state.token_count = TokenCounter.estimate_messages(state.messages)

        # Build tool schemas for LLM
        tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": {"type": "object", "properties": s.parameters},
                },
            }
            for s in tool_specs
        ]

        # --- Plan branch (tier ≤ 2) ---
        plan = None
        if self._strategy.task_planning:
            plan = await self._planner.maybe_plan(
                goal, tier=self._strategy.tier, adapter=self._adapter, available_tools=tool_specs
            )
            if plan is not None:
                yield AgentEvent(type="plan", data={
                    "tasks": [{"id": t.id, "description": t.description} for t in plan.tasks],
                })

        # --- Main loop ---
        plan_tasks = list(self._planner.schedule(plan)) if plan else [None]
        for task in plan_tasks:
            if task is not None:
                yield AgentEvent(type="task_update", data={
                    "id": task.id, "description": task.description, "status": "in_progress",
                })
                # Inject task context into messages
                state.messages.append(Message(
                    role="user",
                    content=f"[任务 {task.id}] {task.description}",
                ))

            while state.turn_count < self._strategy.max_turns:
                state.turn_count += 1

                # Check if compaction needed
                if self._strategy.context_compact and self._context_mgr.should_compact(
                    state.token_count, self._adapter.context_window_size()
                ):
                    state.messages = await self._context_mgr.compact(state.messages, self._adapter)
                    state.token_count = TokenCounter.estimate_messages(state.messages)

                # Select adapter via SensitivityRouter
                active_adapter = self._adapter
                if self._sensitivity_router is not None:
                    active_adapter = self._sensitivity_router.route(state, tool_specs)

                # Call LLM
                try:
                    resp = await active_adapter.chat(LLMRequest(
                        messages=state.messages,
                        tools=tool_schemas if tool_schemas else None,
                        stream=False,
                    ))
                except Exception as exc:
                    state.error_count += 1
                    logger.error("LLM call failed (attempt %d): %s", state.error_count, exc)
                    if state.error_count >= 3:
                        yield AgentEvent(type="error", data={"message": f"LLM 调用失败: {exc}"})
                        break
                    continue

                state.token_count += (resp.usage.input_tokens + resp.usage.output_tokens)

                # Handle response
                if resp.content and resp.tool_calls:
                    # LLM produced thinking text alongside tool calls
                    yield AgentEvent(type="thinking", data={"content": resp.content})

                if resp.tool_calls:
                    # Tool calls
                    state.messages.append(Message(role="assistant", content=resp.content, tool_calls=resp.tool_calls))

                    for tc in resp.tool_calls:
                        yield AgentEvent(type="tool_call", data={"tool": tc.name, "args": tc.arguments, "id": tc.id})

                    # Execute tools
                    batches = self._orchestrator.partition(resp.tool_calls)
                    if not self._strategy.parallel_tools:
                        from edu_cloud.ai.tool_executor import ToolBatch
                        batches = [ToolBatch(calls=[c], concurrent=False) for c in resp.tool_calls]

                    results = await self._orchestrator.execute(batches, ctx)

                    # Notify SensitivityRouter of executed tools (channel lock)
                    for tc, result in zip(resp.tool_calls, results):
                        spec = self._registry.get(tc.name)
                        if spec and self._sensitivity_router:
                            self._sensitivity_router.on_tool_executed(state, spec)

                        state.messages.append(Message(
                            role="tool",
                            content=str(result.to_dict()),
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))
                        yield AgentEvent(type="tool_result", data={
                            "tool": tc.name, "id": tc.id, "success": result.success,
                            "data": result.data, "error": result.error,
                        })

                    state.error_count = 0
                    continue

                if resp.stop_reason == "end_turn" and resp.content:
                    # Direct answer — if in plan mode, mark task complete and break inner loop
                    state.messages.append(Message(role="assistant", content=resp.content))
                    if task is not None:
                        yield AgentEvent(type="task_update", data={
                            "id": task.id, "status": "completed",
                        })
                    else:
                        yield AgentEvent(type="answer", data={"content": resp.content})
                    break

                # No content and no tool calls — unexpected
                logger.warning("LLM returned empty response at turn %d", state.turn_count)
                break

            # Check if error threshold was hit
            if state.error_count >= 3:
                break

        # If plan mode, emit final answer from last assistant message
        if plan is not None and state.messages:
            last_assistant = next(
                (m for m in reversed(state.messages) if m.role == "assistant" and m.content),
                None,
            )
            if last_assistant:
                yield AgentEvent(type="answer", data={"content": last_assistant.content})

        # --- Post-loop: memory extraction ---
        if self._strategy.memory_extract and self._memory_extractor is not None:
            try:
                await self._memory_extractor.extract(state.messages, self._adapter)
            except Exception:
                logger.warning("Post-loop memory extraction failed")

        yield AgentEvent(type="done", data={
            "turns": state.turn_count,
            "tokens": state.token_count,
            "channel": state.channel,
        })
