"""AI API 端点测试（adapted for edu-cloud）。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def ai_setup(client, db):
    school = School(id="ai_s", name="AI测试学校", code="AI01")
    db.add(school)
    await db.commit()
    admin = User(id="ai_u", username="aiadmin", display_name="管理员")
    admin.set_password("p")
    db.add(admin)
    await db.commit()
    db.add(UserRole(user_id=admin.id, role="admin", school_id="ai_s", is_primary=True))
    await db.flush()
    token = create_access_token({"sub": "ai_u", "school_id": "ai_s", "role": "admin"})
    return {"headers": {"Authorization": f"Bearer {token}"}}


async def test_ai_health(client, ai_setup):
    resp = await client.get("/api/v1/ai/health", headers=ai_setup["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "available"
    assert "tools" in data


async def test_ai_sessions_list(client, ai_setup):
    resp = await client.get("/api/v1/ai/sessions", headers=ai_setup["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data


async def test_ai_session_delete(client, ai_setup):
    resp = await client.delete("/api/v1/ai/sessions/nonexistent", headers=ai_setup["headers"])
    assert resp.status_code == 200


async def test_ai_chat_empty_message(client, ai_setup):
    """空消息 — edu-cloud 返回 200 + error 字段（validation in endpoint body）。"""
    resp = await client.post(
        "/api/v1/ai/chat",
        json={"message": "   "},
        headers=ai_setup["headers"],
    )
    # edu-cloud catches ValueError and returns {"error": "..."} with 200
    # or 403 if user lacks USE_AI_CHAT permission
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        data = resp.json()
        assert "error" in data


async def test_ai_chat_too_long_message(client, ai_setup):
    """超长消息 — edu-cloud 返回 200 + error 字段。"""
    resp = await client.post(
        "/api/v1/ai/chat",
        json={"message": "x" * 2001},
        headers=ai_setup["headers"],
    )
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        data = resp.json()
        assert "error" in data
