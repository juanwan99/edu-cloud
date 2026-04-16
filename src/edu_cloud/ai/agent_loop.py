"""Core agent loop — plan, execute tools, verify, respond (Design §3).

Implements the full state machine: CapabilityProbe → SensitivityRouter →
plan branch (tier ≤ 2) → tool execution → thinking/plan/task_update events →
error threshold → memory extract.

Inspired by Claude Code's query.ts AsyncGenerator pattern.
"""
from __future__ import annotations

import json as _json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

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


def _canonicalize(value: Any) -> Any:
    """Canonicalize dict keys for fingerprinting."""
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


@dataclass
class AgentState:
    messages: list[Message]
    turn_count: int = 0
    token_count: int = 0
    llm_error_streak: int = 0
    tool_fail_streak: int = 0
    channel: str = "primary"
    _recent_calls: list[tuple[str, str, str]] = field(default_factory=list)
    # Each entry: (tool_name, args_fingerprint, error_text_or_empty)


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
        history: list[Message] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        state = AgentState(messages=[])

        # Build initial messages
        if system_prompt:
            state.messages.append(Message(role="system", content=system_prompt))
        # Inject multi-turn history (between system prompt and current user message)
        if history:
            state.messages.extend(history)
        state.messages.append(Message(role="user", content=goal))
        state.token_count = TokenCounter.estimate_messages(state.messages)

        # Build tool schemas for LLM
        tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters if "type" in s.parameters else {"type": "object", "properties": s.parameters},
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
                    state.llm_error_streak += 1
                    logger.error("LLM call failed (streak %d): %s", state.llm_error_streak, exc)
                    if state.llm_error_streak >= 3:
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
                        yield AgentEvent(type="tool_call", data={"tool": tc.name, "arguments": tc.arguments})

                    # P2-3: loop detection — skip consecutive duplicate failed calls
                    # Design §4: all 4 conditions must match: same name + same params + consecutive + same error text
                    skipped_ids: set[str] = set()
                    for tc in resp.tool_calls:
                        fp = _json.dumps(_canonicalize(tc.arguments), ensure_ascii=False, sort_keys=True)
                        consecutive_fails = 0
                        last_error: str | None = None
                        for name, args_fp, err in reversed(state._recent_calls):
                            if name == tc.name and args_fp == fp and err:
                                if last_error is None:
                                    last_error = err
                                if err == last_error:
                                    consecutive_fails += 1
                                else:
                                    break  # different error text — not same failure mode
                            else:
                                break  # chain broken
                        if consecutive_fails >= 2:
                            skipped_ids.add(tc.id)
                            state.messages.append(Message(
                                role="tool",
                                content='{"success": false, "error": "skipped: duplicate tool call"}',
                                tool_call_id=tc.id,
                                name=tc.name,
                            ))
                            yield AgentEvent(type="tool_result", data={
                                "tool": tc.name, "result": {"error": "skipped: duplicate tool call"},
                            })

                    # Filter out skipped calls before execution
                    active_calls = [tc for tc in resp.tool_calls if tc.id not in skipped_ids]

                    # Execute tools
                    batches = self._orchestrator.partition(active_calls)
                    if not self._strategy.parallel_tools:
                        from edu_cloud.ai.tool_executor import ToolBatch
                        batches = [ToolBatch(calls=[c], concurrent=False) for c in active_calls]

                    results = await self._orchestrator.execute(batches, ctx)

                    # Update recent_calls for loop detection
                    for tc, result in zip(active_calls, results):
                        fp = _json.dumps(_canonicalize(tc.arguments), ensure_ascii=False, sort_keys=True)
                        error_text = result.error if (not result.success and result.error) else ""
                        state._recent_calls.append((tc.name, fp, error_text))
                        if len(state._recent_calls) > 9:
                            state._recent_calls = state._recent_calls[-9:]

                    # Notify SensitivityRouter of executed tools (channel lock)
                    anonymizer = ctx.anonymizer
                    for tc, result in zip(active_calls, results):
                        spec = self._registry.get(tc.name)
                        if spec and self._sensitivity_router:
                            self._sensitivity_router.on_tool_executed(state, spec)

                        # F003: anonymize tool result data before writing to messages
                        result_dict = result.to_dict()
                        if anonymizer and result.success and result.data:
                            result_dict["data"] = anonymizer.anonymize(result.data)
                        state.messages.append(Message(
                            role="tool",
                            content=str(result_dict),
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))
                        # Legacy compat: emit raw result (data on success, {"error": ...} on failure)
                        # SSE events use original (non-anonymized) data for frontend display
                        legacy_result = result.data if result.success else {"error": result.error}
                        yield AgentEvent(type="tool_result", data={
                            "tool": tc.name, "result": legacy_result,
                        })

                    # P0-4: per-turn tool fail streak (skip-only turns don't count)
                    all_failed = results and all(not r.success for r in results)
                    any_succeeded = any(r.success for r in results)
                    if all_failed:
                        state.tool_fail_streak += 1
                        logger.warning("All tools failed this turn (streak %d)", state.tool_fail_streak)
                        if state.tool_fail_streak >= 3:
                            yield AgentEvent(type="error", data={
                                "message": "工具连续失败，停止执行",
                            })
                            break
                    elif any_succeeded:
                        state.tool_fail_streak = 0

                    # Reset LLM streak on successful LLM response (tool branch = LLM succeeded)
                    state.llm_error_streak = 0
                    continue

                if resp.stop_reason == "end_turn" and resp.content:
                    state.llm_error_streak = 0  # P0-4: successful LLM response
                    # Direct answer — if in plan mode, mark task complete and break inner loop
                    state.messages.append(Message(role="assistant", content=resp.content))
                    # F003: deanonymize answer text (replace codes with real names)
                    answer_text = resp.content
                    if ctx.anonymizer:
                        answer_text = ctx.anonymizer.deanonymize(answer_text)
                    if task is not None:
                        yield AgentEvent(type="task_update", data={
                            "id": task.id, "status": "completed",
                        })
                    else:
                        yield AgentEvent(type="answer", data={"content": answer_text})
                    break

                # No content and no tool calls — unexpected
                logger.warning("LLM returned empty response at turn %d", state.turn_count)
                break

            # Check if error threshold was hit
            if state.llm_error_streak >= 3 or state.tool_fail_streak >= 3:
                break

        # If plan mode, emit final answer from last assistant message
        if plan is not None and state.messages:
            last_assistant = next(
                (m for m in reversed(state.messages) if m.role == "assistant" and m.content),
                None,
            )
            if last_assistant:
                answer_text = last_assistant.content
                if ctx.anonymizer:
                    answer_text = ctx.anonymizer.deanonymize(answer_text)
                yield AgentEvent(type="answer", data={"content": answer_text})

        # --- Post-loop: memory extraction ---
        if self._strategy.memory_extract and self._memory_extractor is not None:
            try:
                await self._memory_extractor.extract(state.messages, self._adapter)
            except Exception:
                logger.warning("Post-loop memory extraction failed")

        # Expose conversation history for multi-turn persistence (F002)
        self._last_messages = [m for m in state.messages if m.role != "system"]

        yield AgentEvent(type="done", data={
            "turns": state.turn_count,
            "tokens": state.token_count,
            "channel": state.channel,
        })

    def get_history(self) -> list[Message]:
        """Return non-system messages from the last run for multi-turn persistence."""
        return getattr(self, "_last_messages", [])

    async def run_as_sub_agent(
        self,
        spec: "AgentSpec",
        goal: str,
        ctx: "ToolContext",
        state: "SharedState",
        system_prompt: str = "",
    ) -> str:
        """Run this AgentLoop as a sub-agent with constrained tools and turns.
        Returns the final answer text (not an event stream).
        """
        from edu_cloud.ai.agent_spec import AgentSpec  # noqa: F811
        from edu_cloud.ai.shared_state import SharedState  # noqa: F811

        # Filter tools to only those in spec
        filtered_specs = self._registry.filter_by_names(spec.tools)

        # Override strategy max_turns with spec.max_turns
        from dataclasses import replace
        sub_strategy = replace(self._strategy, max_turns=spec.max_turns, task_planning=False)
        original_strategy = self._strategy
        self._strategy = sub_strategy

        # Inject shared state context into system prompt
        state_context = ""
        state_dict = state.as_dict()
        if state_dict:
            state_context = f"\n\n当前已知信息：\n{state_dict}"

        final_answer = ""
        try:
            async for event in self.run(
                goal=goal,
                ctx=ctx,
                tool_specs=filtered_specs,
                system_prompt=system_prompt + state_context,
            ):
                if event.type == "answer":
                    final_answer = event.data.get("content", "")
        finally:
            self._strategy = original_strategy

        return final_answer
