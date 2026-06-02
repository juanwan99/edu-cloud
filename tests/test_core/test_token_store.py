"""token_store 单元测试"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_is_revoked_logs_when_redis_unavailable():
    """Redis 不可用时 is_revoked 应记录 warning"""
    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=None):
        with patch("edu_cloud.core.token_store.logger") as mock_logger:
            from edu_cloud.core.token_store import is_revoked
            result = await is_revoked("test-jti")
            assert result is False
            mock_logger.warning.assert_called_once()
            assert "fail-open" in str(mock_logger.warning.call_args).lower()


@pytest.mark.asyncio
async def test_revoke_token_logs_when_redis_unavailable():
    """Redis 不可用时 revoke_token 应记录 warning"""
    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=None):
        with patch("edu_cloud.core.token_store.logger") as mock_logger:
            from edu_cloud.core.token_store import revoke_token
            result = await revoke_token("test-jti")
            assert result is False
            mock_logger.warning.assert_called_once()
