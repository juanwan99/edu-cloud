import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from edu_cloud.ai.runtime import AgentRuntime, AgentContext


@dataclass(frozen=True)
class MockDataScope:
    visible_class_ids: list[str] | None = None
    visible_student_ids: list[str] | None = None


class TestAgentContext:
    def test_create(self):
        ctx = AgentContext(
            db=MagicMock(),
            user_id="u1",
            school_id="sch1",
            role="subject_teacher",
            data_scope=MockDataScope(),
            session_id="sess1",
            user_slots=[],
            system_slots=[],
            enhanced_enabled=False,
        )
        assert ctx.school_id == "sch1"
        assert not ctx.enhanced_enabled

    def test_frozen(self):
        ctx = AgentContext(
            db=MagicMock(), user_id="u1", school_id="sch1",
            role="teacher", data_scope=MockDataScope(),
            session_id="s1", user_slots=[], system_slots=[],
            enhanced_enabled=False,
        )
        with pytest.raises(AttributeError):
            ctx.school_id = "other"

    def test_has_anonymizer_field(self):
        ctx = AgentContext(
            db=MagicMock(), user_id="u1", school_id="sch1",
            role="teacher", data_scope=MockDataScope(),
            session_id="s1", user_slots=[], system_slots=[],
            enhanced_enabled=False, anonymizer=MagicMock(),
        )
        assert ctx.anonymizer is not None


class TestAgentRuntime:
    @pytest.mark.asyncio
    async def test_run_yields_events(self):
        from edu_cloud.ai.schemas import AgentEvent

        mock_event = AgentEvent(type="answer", data={"content": "回答"})
        mock_done = AgentEvent(type="done", data={})

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            instance = MockSup.return_value
            async def mock_handle(**kwargs):
                yield mock_event
                yield mock_done
            instance.handle = mock_handle

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=2)

                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.context_window_size.return_value = 128000
                    MockAdapter.return_value.close = AsyncMock()

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                        system_slots=[], enhanced_enabled=False,
                    )

                    events = []
                    async for event in runtime.run("test", ctx):
                        events.append(event)

                    assert len(events) >= 1
                    assert any(e.type == "answer" for e in events)

    @pytest.mark.asyncio
    async def test_run_model_router_standard(self):
        with patch("edu_cloud.ai.runtime.ModelRouter") as MockRouter:
            from edu_cloud.ai.model_router import ModelChoice
            MockRouter.return_value.route.return_value = ModelChoice(
                slots=[MagicMock()], tier="standard"
            )

            with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
                async def mock_handle(**kwargs):
                    from edu_cloud.ai.schemas import AgentEvent
                    yield AgentEvent(type="done", data={})
                MockSup.return_value.handle = mock_handle

                with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                    MockProbe.return_value.determine_tier = AsyncMock(return_value=3)

                    with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter2:
                        MockAdapter2.return_value.close = AsyncMock()
                        runtime = AgentRuntime()
                        ctx = AgentContext(
                            db=MagicMock(), user_id="u1", school_id="sch1",
                            role="teacher", data_scope=MockDataScope(),
                            session_id="s1",
                            user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                            system_slots=[], enhanced_enabled=False,
                        )

                        async for _ in runtime.run("hello", ctx):
                            pass

                        MockRouter.return_value.route.assert_called_once()


class TestOutputValidatorIntegration:
    @pytest.mark.asyncio
    async def test_validator_called_on_answer(self):
        """F001: OutputValidator must be called when answer event contains data."""
        from edu_cloud.ai.schemas import AgentEvent

        tool_event = AgentEvent(type="tool_result", data={"data": {"avg": 72.3}})
        answer_event = AgentEvent(type="answer", data={"content": "平均分 85 分"})
        done_event = AgentEvent(type="done", data={})

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                yield tool_event
                yield answer_event
                yield done_event
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = []
            MockSup.return_value.model_tier = "tier3"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=3)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.close = AsyncMock()

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                        system_slots=[], enhanced_enabled=False,
                    )

                    with patch.object(
                        runtime._validator, "validate", wraps=runtime._validator.validate
                    ) as mock_validate:
                        events = []
                        async for event in runtime.run("test", ctx):
                            events.append(event)

                        # Validator must have been called with the answer content
                        mock_validate.assert_called_once()
                        call_args = mock_validate.call_args
                        assert "85" in call_args[0][0] or "85" in str(call_args)


class TestRuntimeReceipt:
    @pytest.mark.asyncio
    async def test_history_saved_after_run(self):
        """F002: runtime must expose history after run."""
        from edu_cloud.ai.schemas import AgentEvent

        mock_history = [{"role": "user", "content": "hi"}]

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                yield AgentEvent(type="done", data={})
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = mock_history
            MockSup.return_value.model_tier = "tier3"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=3)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.close = AsyncMock()

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock()],
                        system_slots=[], enhanced_enabled=False,
                    )

                    async for _ in runtime.run("hello", ctx):
                        pass

                    assert runtime.get_last_history() == mock_history
                    run_info = runtime.get_last_run_info()
                    assert run_info is not None
                    assert "model_tier" in run_info

    @pytest.mark.asyncio
    async def test_adapter_closed_after_run(self):
        """F005: adapter must be closed after run completes."""
        from edu_cloud.ai.schemas import AgentEvent

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                yield AgentEvent(type="done", data={})
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = []
            MockSup.return_value.model_tier = "tier3"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=3)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    mock_close = AsyncMock()
                    MockAdapter.return_value.close = mock_close

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock()],
                        system_slots=[], enhanced_enabled=False,
                    )

                    async for _ in runtime.run("hello", ctx):
                        pass

                    mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_info_contains_tools_and_model(self):
        """F004: run_info must contain tools_resolved and model_used."""
        from edu_cloud.ai.schemas import AgentEvent

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                yield AgentEvent(type="done", data={})
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = []
            MockSup.return_value.model_tier = "tier2"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=2)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.close = AsyncMock()

                    runtime = AgentRuntime()
                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock()],
                        system_slots=[], enhanced_enabled=False,
                    )

                    async for _ in runtime.run("hello", ctx):
                        pass

                    run_info = runtime.get_last_run_info()
                    assert run_info is not None
                    assert "tools_resolved" in run_info
                    assert isinstance(run_info["tools_resolved"], list)
                    assert "model_used" in run_info
                    assert "model_tier" in run_info
                    assert run_info["model_tier"] == "tier2"


class TestOutputValidatorWiring:
    """P0-1: OutputValidator must collect tool_result events via runtime entry."""

    @pytest.mark.asyncio
    async def test_validator_collects_from_result_key(self):
        """AgentRuntime.run() must feed tool_result['result'] to OutputValidator.

        Before fix: runtime looks for 'data' key — collected_tool_results is always empty.
        After fix: runtime reads 'result' key — validator gets actual tool data.
        """
        from edu_cloud.ai.schemas import AgentEvent
        from edu_cloud.ai.tool_context import ToolResult

        # Mock events matching agent_loop.py:186 format: {"tool": ..., "result": ...}
        mock_events = [
            AgentEvent(type="tool_result", data={
                "tool": "get_exam_scores",
                "result": {"avg_score": 85.3},
            }),
            AgentEvent(type="answer", data={"content": "平均分 99 分"}),
            AgentEvent(type="done", data={"turns": 1, "tokens": 100, "channel": "primary"}),
        ]

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                for e in mock_events:
                    yield e
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = []
            MockSup.return_value.model_tier = "tier3"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=3)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.close = AsyncMock()
                    MockAdapter.return_value.context_window_size.return_value = 128000

                    runtime = AgentRuntime()

                    # Spy on validator to capture what it receives
                    captured_results = []
                    original_validate = runtime._validator.validate
                    def spy_validate(response, tool_results):
                        captured_results.extend(tool_results)
                        return original_validate(response, tool_results)
                    runtime._validator.validate = spy_validate

                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                        system_slots=[], enhanced_enabled=False,
                    )

                    events = []
                    async for event in runtime.run("test", ctx):
                        events.append(event)

        # KEY ASSERTION: validator received tool data (non-empty)
        assert len(captured_results) > 0, \
            "OutputValidator received no tool results — wiring bug still present"
        assert captured_results[0].data["avg_score"] == 85.3

    @pytest.mark.asyncio
    async def test_validator_filters_error_payload(self):
        """Error tool results must NOT be collected for validation."""
        from edu_cloud.ai.schemas import AgentEvent

        mock_events = [
            AgentEvent(type="tool_result", data={
                "tool": "get_scores",
                "result": {"error": "404 not found"},
            }),
            AgentEvent(type="answer", data={"content": "无数据"}),
            AgentEvent(type="done", data={}),
        ]

        with patch("edu_cloud.ai.runtime.Supervisor") as MockSup:
            async def mock_handle(**kwargs):
                for e in mock_events:
                    yield e
            MockSup.return_value.handle = mock_handle
            MockSup.return_value.get_history.return_value = []
            MockSup.return_value.model_tier = "tier3"

            with patch("edu_cloud.ai.runtime.CapabilityProbe") as MockProbe:
                MockProbe.return_value.determine_tier = AsyncMock(return_value=3)
                with patch("edu_cloud.ai.runtime.LLMProxyAdapter") as MockAdapter:
                    MockAdapter.return_value.close = AsyncMock()
                    MockAdapter.return_value.context_window_size.return_value = 128000

                    runtime = AgentRuntime()
                    captured_results = []
                    original_validate = runtime._validator.validate
                    def spy_validate(response, tool_results):
                        captured_results.extend(tool_results)
                        return original_validate(response, tool_results)
                    runtime._validator.validate = spy_validate

                    ctx = AgentContext(
                        db=MagicMock(), user_id="u1", school_id="sch1",
                        role="teacher", data_scope=MockDataScope(),
                        session_id="s1",
                        user_slots=[MagicMock(api_url="http://test", slot_number=1)],
                        system_slots=[], enhanced_enabled=False,
                    )

                    async for _ in runtime.run("test", ctx):
                        pass

        # Error payloads should NOT be collected
        assert len(captured_results) == 0, \
            "Error payload was collected — should be filtered"


class TestApiLayerWiring:
    """Verify ai.py wiring to EduAgentRuntime (updated for Pydantic AI engine)."""

    def test_api_finally_reads_history(self):
        """History writeback must use runtime.last_messages property."""
        import inspect
        from edu_cloud.api import ai as ai_module

        source = inspect.getsource(ai_module.ai_chat)
        assert "runtime.last_messages" in source, "ai.py must read runtime.last_messages"
        assert "session_state.history" in source, "ai.py must write back to session_state.history"

    def test_api_uses_edu_agent_runtime(self):
        """ai.py must construct EduAgentRuntime, not old AgentRuntime."""
        import inspect
        from edu_cloud.api import ai as ai_module

        source = inspect.getsource(ai_module.ai_chat)
        assert "EduAgentRuntime" in source, "ai.py must use EduAgentRuntime"
        assert "AgentRuntime()" not in source, "ai.py must NOT use old AgentRuntime()"


class TestWorkerEntry:
    def test_worker_function_registered(self):
        from edu_cloud.worker import WorkerSettings
        func_names = [f.__name__ if callable(f) else f.coroutine.__name__
                      for f in WorkerSettings.functions]
        assert "run_agent_scheduled" in func_names

    def test_scheduled_prompts_exist(self):
        from edu_cloud.ai.prompts import SCHEDULED_PROMPTS
        assert "exam_analysis" in SCHEDULED_PROMPTS
