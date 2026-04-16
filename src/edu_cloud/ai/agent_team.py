# src/edu_cloud/ai/agent_team.py
"""AgentTeam: group of sub-agents with shared state and execution strategy."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.shared_state import SharedState

logger = logging.getLogger(__name__)


@dataclass
class AgentTeam:
    """A named group of sub-agents that collaborate on a task domain."""
    name: str
    description: str
    agents: list[AgentSpec]
    execution: str = "sequential"

    @property
    def agent_names(self) -> list[str]:
        return [a.name for a in self.agents]

    @property
    def all_tools(self) -> set[str]:
        result: set[str] = set()
        for a in self.agents:
            result.update(a.tools)
        return result


class TeamRegistry:
    """Registry for available AgentTeams."""
    def __init__(self) -> None:
        self._teams: dict[str, AgentTeam] = {}

    def register(self, team: AgentTeam) -> None:
        if team.name in self._teams:
            raise ValueError(f"Team '{team.name}' already registered")
        self._teams[team.name] = team
        logger.info("Registered team: %s (%d agents)", team.name, len(team.agents))

    def get(self, name: str) -> AgentTeam | None:
        return self._teams.get(name)

    def list_teams(self) -> list[str]:
        return list(self._teams.keys())

    def match_by_tools(self, tool_names: list[str]) -> AgentTeam | None:
        tool_set = set(tool_names)
        best: AgentTeam | None = None
        best_overlap = 0
        for team in self._teams.values():
            overlap = len(team.all_tools & tool_set)
            if overlap > best_overlap:
                best = team
                best_overlap = overlap
        return best

    def get_descriptions(self) -> list[dict[str, str]]:
        return [
            {"name": t.name, "description": t.description}
            for t in self._teams.values()
        ]


class TeamExecutor:
    """Executes an AgentTeam's sub-agents according to execution strategy."""
    async def run(self, team: AgentTeam, goal: str, state: SharedState, **kwargs: Any) -> list[str]:
        if not team.agents:
            return []
        if team.execution == "sequential":
            return await self._run_sequential(team, goal, state, **kwargs)
        logger.warning("Execution mode '%s' not implemented, falling back to sequential", team.execution)
        return await self._run_sequential(team, goal, state, **kwargs)

    async def _run_sequential(self, team: AgentTeam, goal: str, state: SharedState, **kwargs: Any) -> list[str]:
        results: list[str] = []
        for spec in team.agents:
            state.set_stage(spec.name)
            try:
                result = await self._run_sub_agent(spec, goal, state, **kwargs)
                results.append(result)
                # F003 fix: write result back to SharedState for next agent
                state.set(f"{spec.name}_result", result)
            except Exception:
                logger.exception("Sub-agent '%s' failed in team '%s'", spec.name, team.name)
                results.append(f"Error: {spec.name} failed")
                state.set(f"{spec.name}_result", f"Error: {spec.name} failed")
        return results

    async def _run_sub_agent(self, spec: AgentSpec, goal: str, state: SharedState, **kwargs: Any) -> str:
        raise NotImplementedError("_run_sub_agent must be wired to AgentLoop")


# Global registry
teams = TeamRegistry()
