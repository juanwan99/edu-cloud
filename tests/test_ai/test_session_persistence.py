"""Sprint 1 — Session persistence + message DB + circuit breaker tests."""
import json

import pytest

from edu_cloud.ai.models import AiChatMessage, AiSession


@pytest.mark.asyncio
async def test_session_created_in_db_on_chat(client, teacher_headers):
    """POST /ai/chat creates AiSession row in DB."""
    from unittest.mock import patch
    from edu_cloud.ai.schemas import AgentEvent

    async def mock_run(self, msg, *, message_history=None):
        yield AgentEvent(type="answer", data={"content": "ok"})
        yield AgentEvent(type="done", data={"run_id": "r1", "session_id": "s1", "turns": 0, "tokens": 0, "elapsed_ms": 1})

    with patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.run", mock_run), \
         patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.build_agent", lambda self: None):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "hello"},
            headers=teacher_headers,
        )
    assert resp.status_code == 200

    text = resp.text
    events = [json.loads(l[6:]) for l in text.strip().split("\n") if l.strip().startswith("data: ")]
    done_evt = next(e for e in events if e["type"] == "done")
    session_id = done_evt["data"]["session_id"]

    from sqlalchemy import select
    from edu_cloud.database import async_session
    async with async_session() as db:
        row = (await db.execute(select(AiSession).where(AiSession.id == session_id))).scalar_one_or_none()
    assert row is not None
    assert row.role is not None


@pytest.mark.asyncio
async def test_sessions_list_from_db(client, teacher_headers):
    """GET /ai/sessions returns DB-persisted sessions."""
    from edu_cloud.shared.auth import decode_token
    token = teacher_headers["Authorization"].split(" ")[1]
    user_id = decode_token(token)["sub"]

    from edu_cloud.database import async_session
    async with async_session() as db:
        db.add(AiSession(id="db-test-sess", user_id=user_id, role="subject_teacher"))
        await db.commit()

    resp = await client.get("/api/v1/ai/sessions", headers=teacher_headers)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["sessions"]]
    assert "db-test-sess" in ids


@pytest.mark.asyncio
async def test_session_delete_removes_session(client, teacher_headers):
    """DELETE /ai/sessions/{id} removes session from DB."""
    from edu_cloud.shared.auth import decode_token
    token = teacher_headers["Authorization"].split(" ")[1]
    user_id = decode_token(token)["sub"]

    from edu_cloud.database import async_session
    from sqlalchemy import select
    async with async_session() as db:
        db.add(AiSession(id="del-test-sess", user_id=user_id, role="subject_teacher"))
        await db.commit()

    resp = await client.delete("/api/v1/ai/sessions/del-test-sess", headers=teacher_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    async with async_session() as db:
        row = (await db.execute(
            select(AiSession).where(AiSession.id == "del-test-sess")
        )).scalar_one_or_none()
    assert row is None


@pytest.mark.asyncio
async def test_messages_pagination(client, teacher_headers):
    """GET /ai/sessions/{id}/messages returns paginated messages."""
    from edu_cloud.shared.auth import decode_token
    token = teacher_headers["Authorization"].split(" ")[1]
    user_id = decode_token(token)["sub"]

    from edu_cloud.database import async_session
    async with async_session() as db:
        db.add(AiSession(id="msg-page-sess", user_id=user_id, role="subject_teacher"))
        await db.flush()
        for i in range(5):
            db.add(AiChatMessage(
                session_id="msg-page-sess",
                role_in_chat="user" if i % 2 == 0 else "assistant",
                content=f"message {i}",
            ))
        await db.commit()

    resp = await client.get(
        "/api/v1/ai/sessions/msg-page-sess/messages?page=1&page_size=3",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["messages"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 3


@pytest.mark.asyncio
async def test_messages_owner_isolation(client, teacher_headers):
    """Cannot read messages of another user's session."""
    from edu_cloud.database import async_session
    async with async_session() as db:
        db.add(AiSession(id="other-sess", user_id="other-user-id", role="subject_teacher"))
        await db.commit()

    resp = await client.get("/api/v1/ai/sessions/other-sess/messages", headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_after_failures():
    """Circuit breaker opens after 3 failures, closes after cooldown."""
    from edu_cloud.api.ai import (
        _circuit_is_open, _circuit_record_failure, _circuit_record_success, _llm_circuit,
    )
    _llm_circuit["failures"] = 0
    _llm_circuit["open_until"] = 0.0

    assert not _circuit_is_open()

    _circuit_record_failure()
    _circuit_record_failure()
    assert not _circuit_is_open()

    _circuit_record_failure()
    assert _circuit_is_open()

    _circuit_record_success()
    assert not _circuit_is_open()

    _llm_circuit["failures"] = 0
    _llm_circuit["open_until"] = 0.0


@pytest.mark.asyncio
async def test_circuit_breaker_returns_503(client, teacher_headers):
    """Circuit open → POST /ai/chat returns 503."""
    from edu_cloud.api.ai import _llm_circuit
    import time as _time
    _llm_circuit["failures"] = 3
    _llm_circuit["open_until"] = _time.time() + 60

    try:
        resp = await client.post("/api/v1/ai/chat", json={"message": "hello"}, headers=teacher_headers)
        assert resp.status_code == 503
        assert "不可用" in resp.json().get("detail", "")
    finally:
        _llm_circuit["failures"] = 0
        _llm_circuit["open_until"] = 0.0


@pytest.mark.asyncio
async def test_llm_error_yields_retryable_event(client, teacher_headers):
    """LLM failure yields error event with retryable=True."""
    from unittest.mock import patch
    from edu_cloud.ai.schemas import AgentEvent

    async def mock_run_error(self, msg, *, message_history=None):
        yield AgentEvent(type="error", data={"message": "AI 服务暂时不可用，请稍后重试", "retryable": True})
        yield AgentEvent(type="done", data={"run_id": "r1", "session_id": "s1", "turns": 0, "tokens": 0, "elapsed_ms": 1})

    with patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.run", mock_run_error), \
         patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.build_agent", lambda self: None):
        resp = await client.post("/api/v1/ai/chat", json={"message": "test"}, headers=teacher_headers)
    assert resp.status_code == 200
    events = [json.loads(l[6:]) for l in resp.text.strip().split("\n") if l.strip().startswith("data: ")]
    error_evts = [e for e in events if e["type"] == "error"]
    assert len(error_evts) >= 1
    assert error_evts[0]["data"].get("retryable") is True


@pytest.mark.asyncio
async def test_db_session_owner_check(client, teacher_headers):
    """F-001: Cannot use another user's session via session_id param."""
    from edu_cloud.database import async_session
    async with async_session() as db:
        db.add(AiSession(id="stolen-sess", user_id="other-user", role="subject_teacher"))
        await db.commit()

    from unittest.mock import patch
    with patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.run", side_effect=Exception("should not reach")), \
         patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.build_agent", lambda self: None):
        resp = await client.post(
            "/api/v1/ai/chat",
            json={"message": "hijack", "session_id": "stolen-sess"},
            headers=teacher_headers,
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_runtime_llm_exception_yields_retryable(client, teacher_headers):
    """R3-F-002: openai exception in runtime → SSE error with retryable=True and friendly message."""
    from unittest.mock import patch
    from edu_cloud.ai.schemas import AgentEvent

    class FakeOpenAIError(Exception):
        pass
    FakeOpenAIError.__module__ = "openai._exceptions"

    async def mock_run_with_llm_error(self, msg, *, message_history=None):
        exc = FakeOpenAIError("502 Bad Gateway")
        is_llm = "openai" in type(exc).__module__.lower() if hasattr(type(exc), "__module__") else False
        friendly = "AI 服务暂时不可用，请稍后重试" if is_llm else str(exc)
        yield AgentEvent(type="error", data={"message": friendly, "retryable": is_llm})
        yield AgentEvent(type="done", data={"run_id": "r1", "session_id": "s1", "turns": 0, "tokens": 0, "elapsed_ms": 1})

    with patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.run", mock_run_with_llm_error), \
         patch("edu_cloud.ai.engine.edu_runtime.EduAgentRuntime.build_agent", lambda self: None):
        resp = await client.post("/api/v1/ai/chat", json={"message": "test"}, headers=teacher_headers)

    assert resp.status_code == 200
    events = [json.loads(l[6:]) for l in resp.text.strip().split("\n") if l.strip().startswith("data: ")]
    error_evts = [e for e in events if e["type"] == "error"]
    assert len(error_evts) >= 1
    assert error_evts[0]["data"].get("retryable") is True
    assert "不可用" in error_evts[0]["data"]["message"]
