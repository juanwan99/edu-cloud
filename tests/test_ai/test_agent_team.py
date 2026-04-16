# tests/test_ai/test_agent_team.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, TeamRegistry, TeamExecutor
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.schemas import AgentEvent


def _make_spec(name: str, tools: list[str] | None = None) -> AgentSpec:
    return AgentSpec(name=name, description=f"{name} agent", tools=tools or [])


class TestAgentTeam:
    def test_create(self):
        team = AgentTeam(
            name="test_team",
            description="Test team",
            agents=[_make_spec("a"), _make_spec("b")],
            execution="sequential",
        )
        assert team.name == "test_team"
        assert len(team.agents) == 2
        assert team.execution == "sequential"

    def test_agent_names(self):
        team = AgentTeam(
            name="t", description="t",
            agents=[_make_spec("x"), _make_spec("y")],
        )
        assert team.agent_names == ["x", "y"]

    def test_all_tools(self):
        team = AgentTeam(
            name="t", description="t",
            agents=[
                _make_spec("a", ["tool_1", "tool_2"]),
                _make_spec("b", ["tool_2", "tool_3"]),
            ],
        )
        assert team.all_tools == {"tool_1", "tool_2", "tool_3"}


class TestTeamRegistry:
    def test_register_and_get(self):
        reg = TeamRegistry()
        team = AgentTeam(name="edu", description="Edu", agents=[_make_spec("a")])
        reg.register(team)
        assert reg.get("edu") is team

    def test_get_missing_returns_none(self):
        reg = TeamRegistry()
        assert reg.get("nonexistent") is None

    def test_register_duplicate_raises(self):
        reg = TeamRegistry()
        team = AgentTeam(name="dup", description="Dup", agents=[_make_spec("a")])
        reg.register(team)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(team)

    def test_list_teams(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(name="a", description="A", agents=[_make_spec("x")]))
        reg.register(AgentTeam(name="b", description="B", agents=[_make_spec("y")]))
        names = reg.list_teams()
        assert sorted(names) == ["a", "b"]

    def test_list_teams_empty(self):
        reg = TeamRegistry()
        assert reg.list_teams() == []

    def test_match_by_tools(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(
            name="data", description="Data",
            agents=[_make_spec("q", ["exam_list", "exam_detail"])],
        ))
        reg.register(AgentTeam(
            name="kb", description="KB",
            agents=[_make_spec("s", ["search_curriculum"])],
        ))
        match = reg.match_by_tools(["exam_list"])
        assert match is not None
        assert match.name == "data"

    def test_match_by_tools_no_match(self):
        reg = TeamRegistry()
        reg.register(AgentTeam(
            name="data", description="Data",
            agents=[_make_spec("q", ["exam_list"])],
        ))
        assert reg.match_by_tools(["unknown_tool"]) is None


class TestTeamExecutor:
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        execution_order = []
        spec_a = _make_spec("agent_a", ["tool_1"])
        spec_b = _make_spec("agent_b", ["tool_2"])
        team = AgentTeam(
            name="test", description="Test",
            agents=[spec_a, spec_b],
            execution="sequential",
        )

        async def mock_run_sub_agent(spec, goal, state, **kwargs):
            execution_order.append(spec.name)
            state.set(f"{spec.name}_done", True)
            return f"Result from {spec.name}"

        executor = TeamExecutor()
        with patch.object(executor, '_run_sub_agent', side_effect=mock_run_sub_agent):
            state = SharedState()
            result = await executor.run(team, "test goal", state)

        assert execution_order == ["agent_a", "agent_b"]
        assert state.get("agent_a_done") is True
        assert state.get("agent_b_done") is True

    @pytest.mark.asyncio
    async def test_empty_agents(self):
        team = AgentTeam(name="empty", description="Empty", agents=[])
        executor = TeamExecutor()
        state = SharedState()
        result = await executor.run(team, "test", state)
        assert result == []
