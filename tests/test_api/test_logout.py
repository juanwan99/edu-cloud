"""logout 端点测试"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_logout_logs_on_revoke_failure(client, admin_headers):
    """撤销失败时应记录 warning 日志"""
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, side_effect=Exception("Redis down")):
        with patch("edu_cloud.api.auth.logger") as mock_logger:
            resp = await client.post("/api/v1/auth/logout", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
            mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_logout_success(client, admin_headers):
    """正常 logout 应返回 ok"""
    resp = await client.post("/api/v1/auth/logout", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
