"""EduAgentRuntime — Pydantic AI-powered agent runtime replacing AgentLoop/Supervisor.

Constructs AgentDeps, builds the Pydantic AI Agent with RBAC-filtered tools,
runs the agent with asyncio.Queue event streaming, and translates output to
SSE-compatible AgentEvent stream that AiSlidePanel consumes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import DeferredToolRequests
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.artifact_manager import ArtifactManager
from edu_cloud.ai.engine.budget import AgentBudget, BudgetExhausted
from edu_cloud.ai.engine.confirmation_broker import ConfirmationBroker
from edu_cloud.ai.engine.policy_guardrail import PolicyToolGuardrail, ToolDenied
from edu_cloud.ai.engine.tool_meta import EduToolMeta
from edu_cloud.ai.engine.trace_recorder import TraceRecorder
from edu_cloud.ai.schemas import AgentEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from edu_cloud.ai.anonymizer import Anonymizer
    from edu_cloud.ai.data_scope import DataScope
    from edu_cloud.ai.memory_store import MemoryStore

logger = logging.getLogger(__name__)

LLM_PROXY_BASE = "http://localhost:8100/v1"

_llm_clients: dict[str, AsyncOpenAI] = {}


def get_llm_client(slot: str) -> AsyncOpenAI:
    if slot not in _llm_clients:
        import httpx
        _llm_clients[slot] = AsyncOpenAI(
            base_url=LLM_PROXY_BASE,
            api_key="unused",
            default_headers={"X-LLM-Slot": slot},
            max_retries=2,
            timeout=httpx.Timeout(180.0, connect=10.0),
        )
    return _llm_clients[slot]


class EduAgentRuntime:
    """Top-level orchestrator: one instance per /api/v1/ai/chat request.

    Lifecycle:
        runtime = EduAgentRuntime(...)
        async for event in runtime.run(message, message_history=history):
            yield sse_format(event)
    """

    def __init__(
        self,
        *,
        db_sessionmaker: async_sessionmaker[AsyncSession],
        user_id: str,
        school_id: str,
        role: str,
        data_scope: DataScope,
        enabled_modules: frozenset[str],
        capabilities: dict[tuple[str, str], bool],
        anonymizer: Anonymizer,
        memory: MemoryStore,
        session_id: str | None = None,
        model_slot: str = "ai-chat",
        system_prompt: str = "",
        tool_meta_registry: dict[str, EduToolMeta] | None = None,
        budget: AgentBudget | None = None,
        tool_functions: list[Any] | None = None,
        confirmation_timeout: float | None = None,
    ):
        self._run_id = uuid.uuid4().hex[:16]
        self._request_id = uuid.uuid4().hex[:12]
        self._session_id = session_id or uuid.uuid4().hex[:16]
        self._model_slot = model_slot
        self._system_prompt = system_prompt
        self._tool_meta_registry = tool_meta_registry or {}
        self._tool_functions = tool_functions or []

        budget = budget or AgentBudget()
        trace = TraceRecorder(
            self._run_id, self._session_id, school_id, user_id, role,
        )
        confirmations = ConfirmationBroker(
            timeout=confirmation_timeout or 300.0,
        )
        artifacts = ArtifactManager(self._run_id, school_id, anonymizer)

        policy = PolicyToolGuardrail(
            role=role,
            enabled_modules=enabled_modules,
            capabilities=capabilities,
            data_scope=data_scope,
            budget=budget,
            trace=trace,
            tool_meta_registry=self._tool_meta_registry,
        )

        self._deps = AgentDeps(
            run_id=self._run_id,
            request_id=self._request_id,
            session_id=self._session_id,
            user_id=user_id,
            school_id=school_id,
            role=role,
            data_scope=data_scope,
            enabled_modules=enabled_modules,
            capabilities=capabilities,
            db_sessionmaker=db_sessionmaker,
            budget=budget,
            policy=policy,
            confirmations=confirmations,
            artifacts=artifacts,
            trace=trace,
            memory=memory,
            anonymizer=anonymizer,
            model_slot=model_slot,
        )

        trace.set_budget(budget)

        self._agent: Agent[AgentDeps, str | DeferredToolRequests] | None = None
        self._last_messages: list[Any] = []
        self._deferred_output: DeferredToolRequests | None = None

    def _build_model(self) -> OpenAIChatModel:
        client = get_llm_client(self._model_slot)
        return OpenAIChatModel(
            "edu-cloud-agent",
            provider=OpenAIProvider(openai_client=client),
        )

    def build_agent(
        self,
        tool_functions: list[Any] | None = None,
    ) -> Agent[AgentDeps, str | DeferredToolRequests]:
        """Construct the Pydantic AI Agent with model, prompt, and filtered tools."""
        tools = tool_functions or self._tool_functions
        model = self._build_model()
        kwargs: dict[str, Any] = dict(
            model=model,
            deps_type=AgentDeps,
            system_prompt=self._system_prompt,
            output_type=str | DeferredToolRequests,
        )
        if tools:
            kwargs["tools"] = tools
        agent: Agent[AgentDeps, str | DeferredToolRequests] = Agent(**kwargs)
        self._agent = agent
        return agent

    async def run(
        self,
        user_message: str,
        *,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the agent and yield SSE-compatible events.

        Uses asyncio.Queue to stream tool_call/tool_result events in real-time
        while agent.run() executes in a background task.
        """
        if self._agent is None:
            self.build_agent()
        agent = self._agent
        assert agent is not None

        t0 = time.monotonic()
        self._deps.trace.record_event("run_start", {"message_length": len(user_message)})

        event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        self._deps.event_queue = event_queue

        yield AgentEvent(type="thinking", data={"content": ""})

        result_box: dict[str, Any] = {}

        async def _agent_task() -> None:
            try:
                result = await agent.run(
                    user_message,
                    deps=self._deps,
                    message_history=message_history,
                    usage_limits=UsageLimits(
                        request_limit=self._deps.budget.max_tool_calls,
                    ),
                )
                result_box["result"] = result
            except (BudgetExhausted, ToolDenied, Exception) as exc:
                result_box["error"] = exc
            finally:
                await event_queue.put(None)

        task = asyncio.create_task(_agent_task())

        try:
            while True:
                ev = await event_queue.get()
                if ev is None:
                    break
                yield ev
        except (GeneratorExit, asyncio.CancelledError):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._deps.event_queue = None
            return

        await task

        self._deps.event_queue = None

        if "error" in result_box:
            exc = result_box["error"]
            if isinstance(exc, BudgetExhausted):
                yield AgentEvent(type="error", data={
                    "message": f"Budget exhausted: {exc.dimension}",
                    "dimension": exc.dimension,
                })
            elif isinstance(exc, ToolDenied):
                yield AgentEvent(type="error", data={
                    "message": str(exc),
                    "tool": exc.tool,
                    "layer": exc.layer,
                })
            else:
                logger.exception("Agent run failed: %s", exc)
                msg, retryable = _classify_error(exc)
                yield AgentEvent(type="error", data={"message": msg, "retryable": retryable})
        else:
            result = result_box["result"]
            if isinstance(result.output, DeferredToolRequests):
                self._deferred_output = result.output
                deferred = result.output
                for approval in deferred.approvals:
                    meta = self._deps.policy.get_meta(approval.tool_name)
                    risk = meta.risk_level if meta else "medium"
                    pc = self._deps.confirmations.request_confirmation(
                        approval.tool_call_id,
                        approval.tool_name,
                        _parse_args(approval.args),
                        risk_level=risk,
                    )
                    from datetime import datetime, timedelta, timezone
                    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=pc.timeout)).isoformat()
                    yield AgentEvent(
                        type="confirmation_required",
                        data={
                            "run_id": self._run_id,
                            "tool_call_id": approval.tool_call_id,
                            "tool_name": approval.tool_name,
                            "args": _parse_args(approval.args),
                            "expires_at": expires_at,
                        },
                    )
                self._last_messages = list(result.all_messages())
            else:
                yield AgentEvent(type="answer", data={"content": result.output})
                self._last_messages = list(result.all_messages())

            if result.usage:
                self._deps.budget.debit_tokens(result.usage.total_tokens or 0)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._deps.trace.record_event("run_end", {"elapsed_ms": elapsed_ms})
        self._deps.trace.flush()
        await self._deps.trace.flush_to_db(self._deps.db_sessionmaker)
        await self._deps.artifacts.flush_to_db(self._deps.db_sessionmaker)

        self._deps.confirmations.purge_resolved()

        assistant_text = None
        if "result" not in result_box:
            pass
        elif isinstance(result_box["result"].output, str):
            assistant_text = result_box["result"].output
        persistence = await self._persist_messages(user_message, assistant_text)

        yield AgentEvent(type="done", data={
            "run_id": self._run_id,
            "session_id": self._session_id,
            "turns": self._deps.budget.used_tool_calls,
            "tokens": self._deps.budget.used_tokens,
            "elapsed_ms": elapsed_ms,
            "persistence": persistence,
        })

    async def resume_after_confirmation(
        self,
        *,
        approved_ids: list[str],
        denied_ids: list[str] | None = None,
        message_history: list[Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Resume agent run after write confirmations are resolved."""
        if self._agent is None or not self._last_messages:
            yield AgentEvent(type="error", data={"message": "No pending confirmations"})
            return

        for cid in approved_ids:
            self._deps.confirmations.approve(cid)
            self._deps.trace.record_event("confirmation_resolved", {
                "confirmation_id": cid, "decision": "approve",
            })
        for cid in (denied_ids or []):
            self._deps.confirmations.deny(cid)
            self._deps.trace.record_event("confirmation_resolved", {
                "confirmation_id": cid, "decision": "deny",
            })

        event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        self._deps.event_queue = event_queue

        history = message_history or self._last_messages
        result_box: dict[str, Any] = {}

        deferred = self._deferred_output
        tool_results = deferred.build_results(
            approve_ids=set(approved_ids),
        ) if deferred else None

        async def _resume_task() -> None:
            try:
                kwargs: dict[str, Any] = dict(
                    deps=self._deps,
                    message_history=history,
                )
                if tool_results is not None:
                    kwargs["deferred_tool_results"] = tool_results
                result = await self._agent.run(**kwargs)
                result_box["result"] = result
            except Exception as exc:
                result_box["error"] = exc
            finally:
                await event_queue.put(None)

        task = asyncio.create_task(_resume_task())

        try:
            while True:
                ev = await event_queue.get()
                if ev is None:
                    break
                yield ev
        except (GeneratorExit, asyncio.CancelledError):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._deps.event_queue = None
            return

        await task
        self._deps.event_queue = None
        self._deferred_output = None

        if "error" in result_box:
            yield AgentEvent(type="error", data={"message": str(result_box["error"])})
        else:
            result = result_box.get("result")
            if result is not None and isinstance(result.output, str):
                yield AgentEvent(type="answer", data={"content": result.output})

        self._deps.trace.flush()
        await self._deps.trace.flush_to_db(self._deps.db_sessionmaker, append_only=True)
        await self._deps.artifacts.flush_to_db(self._deps.db_sessionmaker)
        self._deps.confirmations.purge_resolved()

        yield AgentEvent(type="done", data={
            "run_id": self._run_id,
            "session_id": self._session_id,
        })

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def deps(self) -> AgentDeps:
        return self._deps

    @property
    def last_messages(self) -> list[Any]:
        return self._last_messages

    @property
    def agent(self) -> Agent[AgentDeps, str | DeferredToolRequests] | None:
        return self._agent


    async def _persist_messages(
        self,
        user_message: str,
        assistant_output: str | None,
        *,
        tool_calls: list[dict] | None = None,
    ) -> dict[str, str]:
        """Write user + assistant messages to DB and report persistence status."""
        try:
            from edu_cloud.ai.models import AiChatMessage
            async with self._deps.db_sessionmaker() as db:
                db.add(AiChatMessage(
                    session_id=self._session_id,
                    role_in_chat="user",
                    content=user_message,
                ))
                if assistant_output:
                    import json as _json
                    meta = _json.dumps({"tool_calls": tool_calls}, ensure_ascii=False) if tool_calls else None
                    db.add(AiChatMessage(
                        session_id=self._session_id,
                        role_in_chat="assistant",
                        content=assistant_output,
                        metadata_json=meta,
                    ))
                await db.commit()
            return {"status": "ok"}
        except Exception as exc:
            logger.warning("Failed to persist chat messages: %s", exc)
            return {"status": "failed", "reason": "chat_history_unavailable"}


def _classify_error(exc: Exception) -> tuple[str, bool]:
    """Classify exception → (user-facing message, retryable flag)."""
    is_llm = "openai" in getattr(type(exc), "__module__", "").lower()
    if is_llm:
        return "AI 服务暂时不可用，请稍后重试", True
    return str(exc), False


def _parse_args(args: str | dict) -> dict:
    if isinstance(args, str):
        try:
            return json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return {"raw": args}
    return args
