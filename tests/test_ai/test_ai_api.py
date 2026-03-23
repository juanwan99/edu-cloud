import pytest


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
    """DELETE /api/v1/ai/sessions/nonexistent returns 200 with deleted: true."""
    resp = await client.delete("/api/v1/ai/sessions/nonexistent", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True


@pytest.mark.asyncio
async def test_ai_session_lifecycle(client, teacher_headers):
    """Seed a session → list shows it → delete it → list no longer shows it."""
    from edu_cloud.api.ai import _sessions, _SessionState
    from edu_cloud.ai.context import AgentContext
    from edu_cloud.ai.anonymizer import Anonymizer

    test_sid = "test-lifecycle-session"
    # Seed a session directly into the in-memory store
    _sessions[test_sid] = _SessionState(
        context=AgentContext(system_content="test"),
        anonymizer=Anonymizer(),
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
