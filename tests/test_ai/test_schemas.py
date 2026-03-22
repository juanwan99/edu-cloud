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
