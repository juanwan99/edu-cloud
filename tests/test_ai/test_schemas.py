from edu_cloud.ai.schemas import ChatMessage, ToolCall, AgentEvent


def test_chat_message_creation():
    msg = ChatMessage(role="user", content="你好")
    assert msg.role == "user"
    assert msg.content == "你好"
    assert msg.tool_calls is None


def test_tool_call_creation():
    tc = ToolCall(id="tc1", name="get_exam_scores", arguments={"exam_id": "e1"})
    assert tc.name == "get_exam_scores"
    assert tc.arguments["exam_id"] == "e1"


def test_agent_event_serialization():
    event = AgentEvent(type="tool_call", data={"tool": "get_exam_scores"})
    d = event.to_dict()
    assert d["type"] == "tool_call"
    assert "tool" in d["data"]


def test_agent_event_answer():
    event = AgentEvent(type="answer", data={"content": "数学平均分 105 分"})
    assert event.type == "answer"


def test_chat_message_to_dict():
    tc = ToolCall(id="tc1", name="test", arguments={"q": "x"})
    msg = ChatMessage(role="assistant", content="thinking", tool_calls=[tc])
    d = msg.to_dict()
    assert d["role"] == "assistant"
    assert d["content"] == "thinking"
    assert len(d["tool_calls"]) == 1
    assert d["tool_calls"][0]["function"]["name"] == "test"


def test_tool_call_from_openai():
    raw = {"id": "tc1", "type": "function", "function": {"name": "test", "arguments": '{"q": "hello"}'}}
    tc = ToolCall.from_openai(raw)
    assert tc.id == "tc1"
    assert tc.name == "test"
    assert tc.arguments == {"q": "hello"}


def test_tool_call_to_openai_roundtrip():
    tc = ToolCall(id="tc1", name="test", arguments={"q": "hello"})
    d = tc.to_openai()
    assert d["id"] == "tc1"
    assert d["function"]["name"] == "test"
    assert '"q"' in d["function"]["arguments"]
