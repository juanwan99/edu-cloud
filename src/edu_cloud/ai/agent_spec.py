"""Sub-agent specification and model slot selection."""

from dataclasses import dataclass, field

_TIER_TO_SLOT = {1: "enhanced", 2: "primary", 3: "basic"}

_COMPLEXITY_TO_SLOT = {
    "reasoning": "enhanced",
    "generation": "enhanced",
    "retrieval": "primary",
    "data_query": "primary",
    "formatting": "basic",
}


@dataclass(frozen=True)
class AgentSpec:
    """Declaration of a sub-agent within an AgentTeam."""

    name: str
    description: str
    tools: list[str]
    model_tier: int | None = None
    max_turns: int = 15
    task_complexity: str = "retrieval"


def select_slot(spec: AgentSpec) -> str:
    """Return the llm-proxy slot name for this agent spec."""
    if spec.model_tier is not None:
        return _TIER_TO_SLOT.get(spec.model_tier, "primary")
    return _COMPLEXITY_TO_SLOT.get(spec.task_complexity, "primary")
