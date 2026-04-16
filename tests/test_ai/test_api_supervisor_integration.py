# tests/test_ai/test_api_supervisor_integration.py
"""Entry-level API test for Supervisor integration (F004/F005 fix)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.supervisor import Supervisor, ClassificationResult
from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.tool_context import ToolContext, ToolResult


class TestSupervisorToolFiltering:
    """F001: Team path must respect ToolAccessResolver filtering."""

    @pytest.mark.asyncio
    async def test_team_sub_agent_only_sees_allowed_tools(self):
        """Sub-agent in team mode should only access tools allowed by ToolAccessResolver."""
        reg = ToolRegistry()

        @reg.register(name="allowed_tool", description="Allowed")
        async def allowed_tool(i: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data="ok")

        @reg.register(name="blocked_tool", description="Blocked")
        async def blocked_tool(i: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data="should not reach")

        adapter = MagicMock(spec=LLMProxyAdapter)
        adapter.context_window_size.return_value = 128_000
        adapter._base_url = "http://test"
        adapter._context_window = 128_000
        adapter.chat = AsyncMock(return_value=LLMResponse(
            content="结果", stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=10),
        ))
        adapter.close = AsyncMock()

        team_reg = TeamRegistry()
        team_reg.register(AgentTeam(
            name="test_team", description="Test",
            agents=[AgentSpec(name="agent_a", description="A",
                              tools=["allowed_tool", "blocked_tool"])],
        ))

        supervisor = Supervisor(
            registry=reg, adapter=adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_reg,
        )

        # Only "allowed_tool" is permitted by ToolAccessResolver
        allowed_specs = reg.filter_by_names(["allowed_tool"])

        with patch.object(supervisor, '_classify',
                          return_value=ClassificationResult(needs_team=True, team_name="test_team")):
            # Capture what tools the sub-agent actually gets
            captured_specs = []

            async def capture_run_as_sub(self_loop, spec, goal, ctx, state, system_prompt=""):
                captured_specs.append(spec.tools)
                return "mocked result"

            with patch('edu_cloud.ai.agent_loop.AgentLoop.run_as_sub_agent', capture_run_as_sub):
                with patch.object(supervisor, '_summarize', new_callable=AsyncMock, return_value="summary"):
                    ctx = MagicMock(spec=ToolContext)
                    ctx.db = None
                    ctx.anonymizer = MagicMock()
                    ctx.anonymizer.anonymize = lambda x: x
                    ctx.anonymizer.deanonymize = lambda x: x

                    events = []
                    async for event in supervisor.handle(
                        message="test", ctx=ctx,
                        tool_specs=allowed_specs,
                        system_prompt="",
                    ):
                        events.append(event)

            # F001 assertion: sub-agent should only see "allowed_tool", not "blocked_tool"
            assert len(captured_specs) == 1
            assert "allowed_tool" in captured_specs[0]
            assert "blocked_tool" not in captured_specs[0]

    @pytest.mark.asyncio
    async def test_deny_all_tools_gives_empty_to_sub_agent(self):
        """When ToolAccessResolver allows NO tools, sub-agent must get empty list."""
        reg = ToolRegistry()

        @reg.register(name="blocked_tool", description="Blocked")
        async def blocked_tool(i: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data="nope")

        adapter = MagicMock(spec=LLMProxyAdapter)
        adapter.context_window_size.return_value = 128_000
        adapter._base_url = "http://test"
        adapter._context_window = 128_000
        adapter.chat = AsyncMock(return_value=LLMResponse(
            content="ok", stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=10),
        ))
        adapter.close = AsyncMock()

        team_reg = TeamRegistry()
        team_reg.register(AgentTeam(
            name="t", description="T",
            agents=[AgentSpec(name="a", description="a", tools=["blocked_tool"])],
        ))

        supervisor = Supervisor(
            registry=reg, adapter=adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_reg,
        )

        # Empty allowed list = deny all
        allowed_specs = []

        captured_specs = []

        async def capture_run(self_loop, spec, goal, ctx, state, system_prompt=""):
            captured_specs.append(spec.tools)
            return "mocked"

        with patch.object(supervisor, '_classify',
                          return_value=ClassificationResult(needs_team=True, team_name="t")):
            with patch('edu_cloud.ai.agent_loop.AgentLoop.run_as_sub_agent', capture_run):
                with patch.object(supervisor, '_summarize', new_callable=AsyncMock, return_value="s"):
                    ctx = MagicMock(spec=ToolContext)
                    ctx.db = None
                    ctx.anonymizer = MagicMock()
                    ctx.anonymizer.anonymize = lambda x: x
                    ctx.anonymizer.deanonymize = lambda x: x

                    async for _ in supervisor.handle(
                        message="test", ctx=ctx,
                        tool_specs=allowed_specs,
                        system_prompt="",
                    ):
                        pass

        assert len(captured_specs) == 1
        assert captured_specs[0] == [], f"Expected empty tools, got {captured_specs[0]}"


class TestSupervisorHistoryPersistence:
    """F002: Team path must preserve multi-turn history."""

    @pytest.mark.asyncio
    async def test_team_dispatch_preserves_prior_history(self):
        from edu_cloud.ai.schemas import Message

        reg = ToolRegistry()

        @reg.register(name="tool_x", description="X")
        async def tool_x(i: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data="x")

        adapter = MagicMock(spec=LLMProxyAdapter)
        adapter.context_window_size.return_value = 128_000
        adapter.chat = AsyncMock(return_value=LLMResponse(
            content="新回答", stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=10),
        ))
        adapter.close = AsyncMock()

        team_reg = TeamRegistry()
        team_reg.register(AgentTeam(
            name="t", description="T",
            agents=[AgentSpec(name="a", description="a", tools=["tool_x"])],
        ))

        supervisor = Supervisor(
            registry=reg, adapter=adapter,
            strategy=LoopStrategy.for_tier(1),
            team_registry=team_reg,
        )

        prior_history = [
            Message(role="user", content="第一个问题"),
            Message(role="assistant", content="第一个回答"),
        ]

        with patch.object(supervisor, '_classify',
                          return_value=ClassificationResult(needs_team=True, team_name="t")):
            with patch.object(supervisor, '_run_team', new_callable=AsyncMock, return_value="团队结果"):
                ctx = MagicMock(spec=ToolContext)
                ctx.db = None
                ctx.anonymizer = MagicMock()
                ctx.anonymizer.anonymize = lambda x: x
                ctx.anonymizer.deanonymize = lambda x: x

                async for _ in supervisor.handle(
                    message="第二个问题", ctx=ctx,
                    tool_specs=reg.get_all_specs(),
                    system_prompt="", history=prior_history,
                ):
                    pass

        history = supervisor.get_history()
        # F002: must include prior history + current turn
        assert len(history) == 4
        assert history[0].content == "第一个问题"
        assert history[1].content == "第一个回答"
        assert history[2].content == "第二个问题"
        assert history[3].role == "assistant"


class TestSharedStateWriteback:
    """F003: Sub-agent results must be written back to SharedState."""

    @pytest.mark.asyncio
    async def test_second_agent_sees_first_agent_result(self):
        from edu_cloud.ai.agent_team import AgentTeam, TeamExecutor
        from edu_cloud.ai.shared_state import SharedState

        spec_a = AgentSpec(name="agent_a", description="A", tools=[])
        spec_b = AgentSpec(name="agent_b", description="B", tools=[])
        team = AgentTeam(name="t", description="T", agents=[spec_a, spec_b])

        seen_by_b = {}

        async def mock_run(spec, goal, state, **kwargs):
            if spec.name == "agent_a":
                return "data from A"
            else:
                # B should see A's result in state
                seen_by_b["a_result"] = state.get("agent_a_result")
                return "data from B"

        executor = TeamExecutor()
        with patch.object(executor, '_run_sub_agent', side_effect=mock_run):
            state = SharedState()
            results = await executor.run(team, "goal", state)

        # F003: second agent must see first agent's result
        assert seen_by_b["a_result"] == "data from A"
        assert state.get("agent_a_result") == "data from A"
        assert state.get("agent_b_result") == "data from B"
