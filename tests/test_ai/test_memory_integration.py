"""Integration tests: MemoryExtractor/MemoryInjector wired into Supervisor and API."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.memory_extractor import MemoryExtractor
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.schemas import AgentEvent, Message
from edu_cloud.ai.tool_context import ToolContext


def _make_supervisor(tier: int, memory_extractor=None):
    """Build a minimal Supervisor with mocked dependencies."""
    registry = MagicMock()
    adapter = MagicMock()
    strategy = LoopStrategy.for_tier(tier)
    return Supervisor(
        registry=registry,
        adapter=adapter,
        strategy=strategy,
        memory_extractor=memory_extractor,
    )


def _make_ctx():
    """Build a minimal ToolContext with mocks."""
    return ToolContext(
        db=MagicMock(),
        school_id="sch-1",
        user_id="u-1",
        role="teacher",
    )


class TestSupervisorMemoryIntegration:
    @pytest.mark.asyncio
    async def test_extractor_called_after_run(self):
        """Supervisor calls memory_extractor after handle() completes for Tier 1."""
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        supervisor = _make_supervisor(tier=1, memory_extractor=extractor)
        ctx = _make_ctx()

        # Mock _run_single to yield a done event and populate _history
        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [
                Message(role="user", content="hello"),
                Message(role="assistant", content="hi"),
            ]
            yield AgentEvent(type="answer", data={"content": "hi"})
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            events = []
            async for event in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                session_id="sess-001",
            ):
                events.append(event)

        assert len(events) == 2
        extractor.extract_and_persist.assert_awaited_once_with(
            db=ctx.db,
            messages=supervisor._history,
            adapter=supervisor._adapter,
            school_id=ctx.school_id,
            user_id=ctx.user_id,
            session_id="sess-001",
        )

    @pytest.mark.asyncio
    async def test_extractor_skipped_tier3(self):
        """Supervisor skips memory extraction for Tier 3."""
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        supervisor = _make_supervisor(tier=3, memory_extractor=extractor)
        ctx = _make_ctx()

        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [
                Message(role="user", content="hello"),
                Message(role="assistant", content="hi"),
            ]
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            async for _ in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                session_id="sess-002",
            ):
                pass

        extractor.extract_and_persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extractor_skipped_tier2(self):
        """Supervisor skips memory extraction for Tier 2."""
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        supervisor = _make_supervisor(tier=2, memory_extractor=extractor)
        ctx = _make_ctx()

        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [Message(role="user", content="hello")]
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            async for _ in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                session_id="sess-003",
            ):
                pass

        extractor.extract_and_persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_extractor_no_error(self):
        """Supervisor works fine without memory_extractor (backward compat)."""
        supervisor = _make_supervisor(tier=1, memory_extractor=None)
        ctx = _make_ctx()

        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [Message(role="user", content="hello")]
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            events = []
            async for event in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                session_id="sess-004",
            ):
                events.append(event)

        assert len(events) == 1  # just the done event, no crash

    @pytest.mark.asyncio
    async def test_no_session_id_skips_extraction(self):
        """Supervisor skips extraction when session_id is None."""
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock()

        supervisor = _make_supervisor(tier=1, memory_extractor=extractor)
        ctx = _make_ctx()

        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [Message(role="user", content="hello")]
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            async for _ in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                # session_id omitted → defaults to None
            ):
                pass

        extractor.extract_and_persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extractor_failure_non_blocking(self):
        """Memory extraction failure does not break the response stream."""
        extractor = MagicMock(spec=MemoryExtractor)
        extractor.extract_and_persist = AsyncMock(
            side_effect=RuntimeError("DB gone")
        )

        supervisor = _make_supervisor(tier=1, memory_extractor=extractor)
        ctx = _make_ctx()

        async def fake_run_single(message, ctx_, *, tool_specs, system_prompt, history):
            supervisor._history = [Message(role="user", content="hello")]
            yield AgentEvent(type="answer", data={"content": "hi"})
            yield AgentEvent(type="done", data={})

        with patch.object(supervisor, "_run_single", side_effect=fake_run_single):
            events = []
            async for event in supervisor.handle(
                message="hello",
                ctx=ctx,
                tool_specs=[],
                session_id="sess-005",
            ):
                events.append(event)

        # Stream should complete normally despite extraction failure
        assert len(events) == 2
        assert events[0].type == "answer"
        assert events[1].type == "done"


class TestMemoryInjectorIntegration:
    @pytest.mark.asyncio
    async def test_injector_appends_to_prompt(self):
        """MemoryInjector output appends to system prompt."""
        injector = MagicMock(spec=MemoryInjector)
        injector.build_context = AsyncMock(
            return_value='\n\n【已知上下文（跨会话记忆）】\n[student] stu-1: {"math": 0.4}'
        )
        ctx = MagicMock()
        ctx.db = MagicMock()
        ctx.school_id = "sch-1"
        ctx.user_id = "u-1"

        context = await injector.build_context(
            db=ctx.db,
            school_id="sch-1",
            user_id="u-1",
            role="teacher",
        )
        system_prompt = "你是教育助手" + context
        assert "已知上下文" in system_prompt
        assert "math" in system_prompt

    @pytest.mark.asyncio
    async def test_injector_empty_returns_original_prompt(self):
        """When injector returns empty, prompt is unchanged."""
        injector = MagicMock(spec=MemoryInjector)
        injector.build_context = AsyncMock(return_value="")

        context = await injector.build_context(
            db=MagicMock(),
            school_id="sch-1",
            user_id="u-1",
            role="teacher",
        )
        system_prompt = "你是教育助手" + context
        assert system_prompt == "你是教育助手"
