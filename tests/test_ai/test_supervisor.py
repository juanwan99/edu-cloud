# tests/test_ai/test_supervisor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor, ClassificationResult
from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_spec(name, tools=None):
    return AgentSpec(name=name, description=f"{name}", tools=tools or [])


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="这是回答",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()
    return adapter


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()

    @reg.register(name="exam_list", description="List exams")
    async def exam_list(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    @reg.register(name="search_curriculum", description="Search curriculum")
    async def search_curriculum(i: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=[])

    return reg


@pytest.fixture
def team_registry():
    reg = TeamRegistry()
    reg.register(AgentTeam(
        name="edu_data",
        description="教育数据分析：考试成绩查询、学情分析、班级对比",
        agents=[_make_spec("data_query", ["exam_list"])],
    ))
    return reg


class TestClassificationResult:
    def test_simple(self):
        r = ClassificationResult(needs_team=False)
        assert not r.needs_team
        assert r.team_name is None

    def test_complex(self):
        r = ClassificationResult(needs_team=True, team_name="edu_data")
        assert r.needs_team
        assert r.team_name == "edu_data"


class TestSupervisorSimple:
    @pytest.mark.asyncio
    async def test_simple_request_uses_single_loop(self, mock_adapter, tool_registry, team_registry):
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=team_registry,
        )

        with patch.object(supervisor, '_classify', return_value=ClassificationResult(needs_team=False)):
            ctx = MagicMock(spec=ToolContext)
            ctx.db = None
            ctx.anonymizer = MagicMock()
            ctx.anonymizer.anonymize = lambda x: x
            ctx.anonymizer.deanonymize = lambda x: x

            events = []
            async for event in supervisor.handle(
                message="你好",
                ctx=ctx,
                tool_specs=tool_registry.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_no_team_fallback(self, mock_adapter, tool_registry):
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
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
            tool_specs=tool_registry.get_all_specs(),
            system_prompt="",
        ):
            events.append(event)

        assert len(events) > 0


class TestSupervisorDispatch:
    @pytest.mark.asyncio
    async def test_complex_request_dispatches_to_team(self, mock_adapter, tool_registry, team_registry):
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_registry,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="edu_data"),
        ):
            with patch.object(supervisor, '_run_team', new_callable=AsyncMock) as mock_run_team:
                mock_run_team.return_value = "团队执行结果"

                ctx = MagicMock(spec=ToolContext)
                ctx.db = None
                ctx.anonymizer = MagicMock()
                ctx.anonymizer.anonymize = lambda x: x
                ctx.anonymizer.deanonymize = lambda x: x

                events = []
                async for event in supervisor.handle(
                    message="分析上次期中考试各班数学成绩并生成对比报告",
                    ctx=ctx,
                    tool_specs=tool_registry.get_all_specs(),
                    system_prompt="",
                ):
                    events.append(event)

                mock_run_team.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_team_fallback(self, mock_adapter, tool_registry, team_registry):
        supervisor = Supervisor(
            registry=tool_registry,
            adapter=mock_adapter,
            strategy=LoopStrategy.for_tier(2),
            team_registry=team_registry,
        )

        with patch.object(
            supervisor, '_classify',
            return_value=ClassificationResult(needs_team=True, team_name="nonexistent"),
        ):
            ctx = MagicMock(spec=ToolContext)
            ctx.db = None
            ctx.anonymizer = MagicMock()
            ctx.anonymizer.anonymize = lambda x: x
            ctx.anonymizer.deanonymize = lambda x: x

            events = []
            async for event in supervisor.handle(
                message="test",
                ctx=ctx,
                tool_specs=tool_registry.get_all_specs(),
                system_prompt="",
            ):
                events.append(event)

            assert len(events) > 0
