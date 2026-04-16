# tests/test_ai/test_backward_compat.py
"""Verify that Supervisor integration doesn't break existing AI chat behavior."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor, ClassificationResult
from edu_cloud.ai.agent_team import TeamRegistry
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def simple_setup():
    reg = ToolRegistry()

    @reg.register(name="exam_list", description="List exams")
    async def exam_list(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="回答内容",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()

    return reg, adapter


class TestBackwardCompat:
    @pytest.mark.asyncio
    async def test_simple_message_returns_answer_event(self, simple_setup):
        reg, adapter = simple_setup
        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=None,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        events = []
        async for event in supervisor.handle(
            message="你好",
            ctx=ctx,
            tool_specs=reg.get_all_specs(),
            system_prompt="你是教育助手",
        ):
            events.append(event)

        event_types = [e.type for e in events]
        assert "answer" in event_types or "done" in event_types

    @pytest.mark.asyncio
    async def test_event_has_to_dict(self, simple_setup):
        reg, adapter = simple_setup
        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=None,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        async for event in supervisor.handle(
            message="你好",
            ctx=ctx,
            tool_specs=reg.get_all_specs(),
            system_prompt="",
        ):
            d = event.to_dict()
            assert "type" in d
            assert "data" in d

    @pytest.mark.asyncio
    async def test_tier3_never_uses_team(self, simple_setup):
        reg, adapter = simple_setup
        team_reg = TeamRegistry()

        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(3),
            team_registry=team_reg,
        )

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        with patch.object(supervisor, '_classify') as mock_classify:
            events = []
            async for event in supervisor.handle(
                message="复杂的多步分析请求",
                ctx=ctx,
                tool_specs=reg.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            mock_classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_team_dispatch_produces_answer_and_done(self, simple_setup):
        """Team dispatch path should produce status + answer + done events."""
        reg, adapter = simple_setup
        team_reg = TeamRegistry()
        team_reg.register(AgentTeam(
            name="edu_data",
            description="教育数据分析",
            agents=[AgentSpec(name="q", description="q", tools=["exam_list"])],
        ))

        supervisor = Supervisor(
            registry=reg,
            adapter=adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_reg,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="edu_data"),
        ):
            with patch.object(supervisor, '_run_team', new_callable=AsyncMock, return_value="分析结果"):
                ctx = MagicMock(spec=ToolContext)
                ctx.db = None
                ctx.anonymizer = MagicMock()
                ctx.anonymizer.anonymize = lambda x: x
                ctx.anonymizer.deanonymize = lambda x: x

                events = []
                async for event in supervisor.handle(
                    message="分析数学成绩",
                    ctx=ctx,
                    tool_specs=reg.get_all_specs(),
                    system_prompt="",
                ):
                    events.append(event)

                event_types = [e.type for e in events]
                assert "status" in event_types, "Team dispatch must emit status event"
                assert "answer" in event_types, "Team dispatch must emit answer event"
                assert "done" in event_types, "Team dispatch must emit done event"

                # F002 fix: verify history is populated
                history = supervisor.get_history()
                assert len(history) == 2
                assert history[0].role == "user"
                assert history[1].role == "assistant"

                # F002 fix: verify model_tier is string
                assert isinstance(supervisor.model_tier, str)
                assert supervisor.model_tier.startswith("tier")
