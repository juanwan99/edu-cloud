import pytest


@pytest.mark.asyncio
async def test_ai_health(client):
    resp = await client.get("/api/v1/ai/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


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
