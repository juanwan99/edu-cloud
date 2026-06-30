import json
import pytest
from types import SimpleNamespace
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
async def test_ai_health_reports_required_action_submit_not_ready_by_default(client):
    resp = await client.get("/api/v1/ai/health")
    coze = resp.json()["provider"]["readiness"]["coze"]
    assert coze["required_action_submit_ready"] is False
    assert coze["tool_modes"]["coze_required_action"] is False


@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client):
    resp = await client.post("/api/v1/ai/chat", json={"message": "你好"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_chat_empty_message(client, teacher_headers):
    resp = await client.post("/api/v1/ai/chat", json={"message": ""}, headers=teacher_headers)
    assert resp.status_code == 422
    data = resp.json()
    assert "消息不能为空" in data.get("detail", "")


@pytest.mark.asyncio
async def test_ai_chat_whitespace_message(client, teacher_headers):
    resp = await client.post("/api/v1/ai/chat", json={"message": "   "}, headers=teacher_headers)
    assert resp.status_code == 422
    data = resp.json()
    assert data.get("detail") == "消息不能为空"


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
    """Seed a session in DB → list shows it → delete it → list no longer shows it."""
    from edu_cloud.api.ai import _sessions
    from edu_cloud.shared.auth import decode_token
    token = teacher_headers["Authorization"].split(" ")[1]
    teacher_user_id = decode_token(token)["sub"]

    test_sid = "test-lifecycle-session"
    from edu_cloud.ai.models import AiSession
    from edu_cloud.database import async_session
    async with async_session() as db:
        db.add(AiSession(id=test_sid, user_id=teacher_user_id, role="subject_teacher"))
        await db.commit()

    try:
        resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()["sessions"]]
        assert test_sid in ids

        resp = await client.delete(f"/api/v1/ai/sessions/{test_sid}", headers=teacher_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
        ids = [s["id"] for s in resp.json()["sessions"]]
        assert test_sid not in ids
    finally:
        _sessions.pop(test_sid, None)


@pytest.mark.asyncio
async def test_ai_session_isolation(client, teacher_headers):
    """Integration F002: sessions are owner-scoped — user cannot see/delete others' sessions."""
    from edu_cloud.ai.models import AiSession
    from edu_cloud.database import async_session

    other_sid = "other-user-session"
    async with async_session() as db:
        db.add(AiSession(id=other_sid, user_id="some-other-user-id", role="subject_teacher"))
        await db.commit()

    resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
    ids = [s["id"] for s in resp.json()["sessions"]]
    assert other_sid not in ids

    resp = await client.delete(f"/api/v1/ai/sessions/{other_sid}", headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ai_chat_sse_stream_via_http(client, teacher_headers):
    """SSE contract test — POST /api/v1/ai/chat streams provider events unchanged."""
    from edu_cloud.ai.schemas import AgentEvent

    class MockRun:
        provider_name = "current_pydantic"
        run_id = "test"
        last_messages = []

        def is_confirmation_expired(self, confirmation_id):
            return True

        async def resume_after_confirmation(self, *, approved_ids, denied_ids=None, message_history=None):
            yield AgentEvent(type="done", data={"run_id": self.run_id})

        async def run(self, user_message, *, message_history=None):
            yield AgentEvent(type="thinking", data={"content": ""})
            yield AgentEvent(type="tool_call", data={"tool": "get_exam_list", "arguments": {}})
            yield AgentEvent(type="tool_result", data={"tool": "get_exam_list"})
            yield AgentEvent(type="answer", data={"content": "考试列表已获取"})
            yield AgentEvent(type="done", data={"run_id": self.run_id, "turns": 1, "tokens": 15})

    async def create_agent_run(settings, context):
        return MockRun()

    with patch("edu_cloud.ai.providers.create_agent_run", create_agent_run):
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


@pytest.mark.asyncio
async def test_ai_chat_datascope_build_failure_fails_closed(client, teacher_headers):
    """POST /api/v1/ai/chat must not create an agent run if DataScope cannot be built."""
    create_agent_run = AsyncMock()

    with patch(
        "edu_cloud.ai.data_scope.DataScopeBuilder.build",
        AsyncMock(side_effect=RuntimeError("datascope unavailable")),
    ), patch("edu_cloud.ai.providers.create_agent_run", create_agent_run):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "list my class results"},
            headers=teacher_headers,
        )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "AI data scope is temporarily unavailable"
    create_agent_run.assert_not_awaited()


def test_provider_history_is_isolated_by_runtime_type():
    from edu_cloud.api.ai import (
        _SessionState,
        _message_history_for_runtime,
        _store_session_history_for_runtime,
    )

    state = _SessionState(anonymizer=None, owner_id="u1")
    state.history = ["pydantic-history"]

    coze_run = SimpleNamespace(
        provider_name="coze",
        last_messages=[{"role": "assistant", "content": "coze"}],
    )
    assert _message_history_for_runtime(state, coze_run) is None
    _store_session_history_for_runtime(state, coze_run)
    assert state.history == ["pydantic-history"]

    pydantic_run = SimpleNamespace(
        provider_name="current_pydantic",
        last_messages=["new-pydantic-history"],
    )
    assert _message_history_for_runtime(state, pydantic_run) == ["pydantic-history"]
    _store_session_history_for_runtime(state, pydantic_run)
    assert state.history == ["new-pydantic-history"]


@pytest.mark.asyncio
async def test_ai_chat_retries_with_fallback_provider_before_answer(client, teacher_headers):
    from edu_cloud.ai.schemas import AgentEvent

    class CozeErrorRun:
        provider_name = "coze"
        run_id = "coze-run"
        last_messages = [{"role": "assistant", "content": ""}]

        def is_confirmation_expired(self, confirmation_id):
            return True

        async def run(self, user_message, *, message_history=None):
            yield AgentEvent(type="thinking", data={"content": ""})
            yield AgentEvent(type="error", data={"message": "coze down", "retryable": True})

    class FallbackRun:
        provider_name = "current_pydantic"
        run_id = "fallback-run"
        last_messages = ["fallback-history"]

        def __init__(self):
            self.message_history_seen = None

        def is_confirmation_expired(self, confirmation_id):
            return True

        async def run(self, user_message, *, message_history=None):
            self.message_history_seen = message_history
            yield AgentEvent(type="answer", data={"content": "fallback answer"})
            yield AgentEvent(type="done", data={"run_id": self.run_id})

    coze_run = CozeErrorRun()
    fallback_run = FallbackRun()

    async def create_agent_run(settings, context):
        return coze_run

    async def create_fallback_agent_run(settings, context):
        return fallback_run

    with patch("edu_cloud.ai.providers.create_agent_run", create_agent_run), \
         patch("edu_cloud.ai.providers.create_fallback_agent_run", create_fallback_agent_run):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "列出考试"},
            headers=teacher_headers,
        )

    assert resp.status_code == 200
    events = [
        json.loads(line.strip()[6:])
        for line in resp.text.strip().split("\n")
        if line.strip().startswith("data: ")
    ]
    assert "coze down" not in resp.text
    assert any(e["type"] == "answer" and e["data"]["content"] == "fallback answer" for e in events)
    done_evt = next(e for e in events if e["type"] == "done")
    assert done_evt["data"]["run_id"] == "fallback-run"
    assert fallback_run.message_history_seen == []


@pytest.mark.asyncio
async def test_ai_chat_uses_configured_coze_provider_via_http_sse(client, teacher_headers, monkeypatch):
    from edu_cloud.api.ai import _sessions
    from edu_cloud.config import settings

    session_id = "coze-provider-e2e-session"
    monkeypatch.setattr(settings, "AI_COZE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_COZE_API_BASE", "http://fake-coze")
    monkeypatch.setattr(settings, "AI_COZE_BOT_ID", "bot-1")
    monkeypatch.setattr(settings, "AI_COZE_API_TOKEN", "pat-test")
    monkeypatch.setattr(settings, "AI_COZE_TIMEOUT", 10)

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield "event: conversation.chat.created"
            yield 'data: {"id":"chat-1","conversation_id":"conv-1","bot_id":"bot-1","status":"created"}'
            yield "event: conversation.message.delta"
            yield 'data: {"id":"msg-1","conversation_id":"conv-1","role":"assistant","type":"answer","content":"coze answer","content_type":"text","chat_id":"chat-1"}'
            yield "event: done"
            yield 'data: "[DONE]"'

    class FakeStream:
        def __init__(self, url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload

        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, method, url, *, headers, json):
            return FakeStream(url, headers, json)

    monkeypatch.setattr("edu_cloud.ai.providers.coze.httpx.AsyncClient", FakeClient)

    try:
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "走 coze", "session_id": session_id},
            headers=teacher_headers,
        )
    finally:
        _sessions.pop(session_id, None)

    assert resp.status_code == 200
    events = [
        json.loads(line.strip()[6:])
        for line in resp.text.strip().split("\n")
        if line.strip().startswith("data: ")
    ]
    assert captured["url"] == "http://fake-coze/v3/chat"
    assert captured["headers"]["Authorization"] == "Bearer pat-test"
    assert captured["payload"]["bot_id"] == "bot-1"
    assert any(e["type"] == "answer" and e["data"]["content"] == "coze answer" for e in events)
    done_evt = next(e for e in events if e["type"] == "done")
    assert done_evt["data"]["provider"] == "coze"
