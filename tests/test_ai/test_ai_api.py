import json
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_ai_health(client):
    resp = await client.get("/api/v1/ai/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "available"


@pytest.mark.asyncio
async def test_ai_health_includes_tool_count(client):
    resp = await client.get("/api/v1/ai/health")
    data = resp.json()
    assert "tools" in data
    assert isinstance(data["tools"], int)
    assert data["tools"] >= 0


@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client):
    resp = await client.post("/api/v1/ai/chat", json={"message": "你好"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_chat_empty_message(client, teacher_headers):
    resp = await client.post("/api/v1/ai/chat", json={"message": ""}, headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data or "消息不能为空" in str(data)


@pytest.mark.asyncio
async def test_ai_chat_empty_message_returns_error_key(client, teacher_headers):
    resp = await client.post("/api/v1/ai/chat", json={"message": "   "}, headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("error") == "消息不能为空"


@pytest.mark.asyncio
async def test_ai_sessions_list(client, teacher_headers):
    """GET /api/v1/ai/sessions returns 200 with a sessions list."""
    resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_ai_sessions_delete(client, teacher_headers):
    """DELETE /api/v1/ai/sessions/nonexistent returns 200 with deleted: false."""
    resp = await client.delete("/api/v1/ai/sessions/nonexistent", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is False


@pytest.mark.asyncio
async def test_ai_session_lifecycle(client, teacher_headers):
    """Seed a session → list shows it → delete it → list no longer shows it."""
    from edu_cloud.api.ai import _sessions, _SessionState
    from edu_cloud.ai.anonymizer import Anonymizer

    # Decode teacher user_id from JWT
    from edu_cloud.shared.auth import decode_token
    token = teacher_headers["Authorization"].split(" ")[1]
    payload = decode_token(token)
    teacher_user_id = payload["sub"]

    test_sid = "test-lifecycle-session"
    # Seed a session directly into the in-memory store with correct owner
    _sessions[test_sid] = _SessionState(
        anonymizer=Anonymizer(),
        owner_id=teacher_user_id,
    )
    try:
        # List should include our session
        resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
        assert resp.status_code == 200
        assert test_sid in resp.json()["sessions"]

        # Delete it
        resp = await client.delete(f"/api/v1/ai/sessions/{test_sid}", headers=teacher_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # List should no longer include it
        resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
        assert test_sid not in resp.json()["sessions"]

        # Also verify in-memory state
        assert test_sid not in _sessions
    finally:
        _sessions.pop(test_sid, None)


@pytest.mark.asyncio
async def test_ai_session_isolation(client, teacher_headers):
    """Integration F002: sessions are owner-scoped — user cannot see/delete others' sessions."""
    from edu_cloud.api.ai import _sessions, _SessionState
    from edu_cloud.ai.anonymizer import Anonymizer

    other_sid = "other-user-session"
    _sessions[other_sid] = _SessionState(
        anonymizer=Anonymizer(),
        owner_id="some-other-user-id",
    )
    try:
        # List should NOT include the other user's session
        resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
        assert other_sid not in resp.json()["sessions"]

        # Delete should be forbidden (403)
        resp = await client.delete(f"/api/v1/ai/sessions/{other_sid}", headers=teacher_headers)
        assert resp.status_code == 403
    finally:
        _sessions.pop(other_sid, None)


@pytest.mark.asyncio
async def test_ai_chat_sse_stream_via_http(client, teacher_headers):
    """SSE contract test — POST /api/v1/ai/chat returns correct SSE event stream via EduAgentRuntime."""
    from edu_cloud.ai.schemas import AgentEvent

    async def mock_run(self, user_message, *, message_history=None):
        yield AgentEvent(type="thinking", data={"content": ""})
        yield AgentEvent(type="tool_call", data={"tool": "get_exam_list", "arguments": {}})
        yield AgentEvent(type="tool_result", data={"tool": "get_exam_list"})
        yield AgentEvent(type="answer", data={"content": "考试列表已获取"})
        yield AgentEvent(type="done", data={"run_id": "test", "session_id": "s1", "turns": 1, "tokens": 15})

    with patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.run", mock_run), \
         patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.build_agent", lambda self: None):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "列出考试"},
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        text = resp.text
        events = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        types = [e["type"] for e in events]
        assert "tool_call" in types, f"Missing tool_call in {types}"
        assert "tool_result" in types, f"Missing tool_result in {types}"
        assert "done" in types, f"Missing done in {types}"

        done_evt = next(e for e in events if e["type"] == "done")
        assert "session_id" in done_evt["data"]

        tc_evt = next(e for e in events if e["type"] == "tool_call")
        assert "tool" in tc_evt["data"]
        assert "id" not in tc_evt["data"]
