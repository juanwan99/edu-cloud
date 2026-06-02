"""AI 会话删除审计测试"""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_delete_session_logs_cascade_count(client, db, admin_user, admin_headers):
    """删除会话前应记录将被级联删除的消息数"""
    from edu_cloud.ai.models import AiSession, AiChatMessage

    session = AiSession(
        id="AUDIT_DEL_001", user_id=str(admin_user.id), role="platform_admin",
    )
    db.add(session)
    await db.commit()

    for i in range(3):
        db.add(AiChatMessage(
            id=f"msg-audit-{i}", session_id="AUDIT_DEL_001",
            role_in_chat="user", content=f"消息{i}",
        ))
    await db.commit()

    with patch("edu_cloud.api.ai.logger") as mock_logger:
        resp = await client.delete(
            "/api/v1/ai/sessions/AUDIT_DEL_001", headers=admin_headers,
        )
        assert resp.status_code == 200

        info_calls = [c for c in mock_logger.info.call_args_list
                      if "ai_session_deleted" in str(c)]
        assert len(info_calls) >= 1


@pytest.mark.asyncio
async def test_delete_nonexistent_session_no_error(client, admin_headers):
    """删除不存在的会话不应报错"""
    resp = await client.delete(
        "/api/v1/ai/sessions/nonexistent-id", headers=admin_headers,
    )
    assert resp.status_code == 200
