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
