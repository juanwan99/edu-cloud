from edu_cloud.ai.schemas import AgentEvent, Message, ToolCall, Transition, ChatMessage


def test_agent_event_new_types():
    for event_type in ("thinking", "plan", "task_update", "tool_call", "tool_result", "answer", "error", "done"):
        e = AgentEvent(type=event_type, data={"test": True})
        d = e.to_dict()
        assert d["type"] == event_type
        assert d["data"]["test"] is True


def test_transition_enum():
    assert Transition.NEXT_TURN.value == "next_turn"
    assert Transition.COMPACT.value == "compact"
    assert Transition.DONE.value == "done"
    assert Transition.ERROR_RETRY.value == "error_retry"
    assert Transition.TIER_DOWNGRADE.value == "tier_downgrade"
    assert Transition.MAX_TURNS.value == "max_turns"
    assert Transition.BUDGET_EXHAUSTED.value == "budget_exhausted"


def test_message_dataclass():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"
    assert m.tool_calls is None

    m2 = Message(role="assistant", content=None, tool_calls=[
        ToolCall(id="tc1", name="get_exam", arguments={"id": "1"}, _raw={})
    ])
    assert len(m2.tool_calls) == 1


def test_message_alias():
    """ChatMessage is an alias for Message (backward compat)."""
    assert ChatMessage is Message


def test_message_to_dict_omits_none_content():
    m = Message(role="assistant", tool_calls=[
        ToolCall(id="tc1", name="test", arguments={"q": "x"})
    ])
    d = m.to_dict()
    assert "content" not in d
    assert len(d["tool_calls"]) == 1
