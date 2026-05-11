"""轻量级状态机注册表 -- 集中声明所有实体的状态转换规则。"""

from edu_cloud.services.exceptions import StateError

STATE_MACHINES: dict[str, dict] = {
    "exam": {
        "states": [
            "draft", "scanning", "grading", "reviewing",
            "completed", "published", "archived",
        ],
        "transitions": {
            "draft": {"scanning"},
            "scanning": {"grading", "draft"},
            "grading": {"reviewing"},
            "reviewing": {"completed"},
            "completed": {"published", "archived"},
            "published": {"archived"},
        },
    },
    "grading_task": {
        "states": ["pending", "processing", "completed", "failed", "cancelled"],
        "transitions": {
            "pending": {"processing", "cancelled"},
            "processing": {"completed", "failed", "cancelled"},
            "failed": {"pending"},  # retry
            # completed and cancelled are terminal states
        },
    },
    "grading_result": {
        "states": ["ai_pending", "ai_done", "confirmed"],
        "transitions": {
            "ai_pending": {"ai_done"},
            "ai_done": {"confirmed", "ai_pending"},  # re-grade allowed
            # confirmed is terminal -- no rollback
        },
    },
    "document": {
        "states": ["draft", "reviewed", "pending", "approved", "rejected", "executed"],
        "transitions": {
            "draft": {"reviewed"},
            "reviewed": {"pending"},
            "pending": {"approved", "rejected"},
            "approved": {"executed"},
            "rejected": {"draft"},
        },
    },
}


def validate_transition(entity_type: str, old_status: str, new_status: str) -> None:
    """Validate that a status transition is legal. Raises StateError if not."""
    machine = STATE_MACHINES.get(entity_type)
    if machine is None:
        return  # unregistered entity types pass through (backward compat)

    allowed = machine["transitions"].get(old_status, set())
    if new_status not in allowed:
        raise StateError(
            f"{entity_type}: {old_status} -> {new_status} "
            f"(allowed: {allowed or 'none (terminal state)'})"
        )


def get_terminal_states(entity_type: str) -> set[str]:
    """Return terminal states (states with no outgoing transitions)."""
    machine = STATE_MACHINES.get(entity_type)
    if machine is None:
        return set()
    all_states = set(machine["states"])
    states_with_transitions = set(machine["transitions"].keys())
    return all_states - states_with_transitions
