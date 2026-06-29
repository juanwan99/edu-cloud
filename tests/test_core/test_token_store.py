"""Unit tests for token revocation storage."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_is_revoked_fail_open_outside_production_when_redis_unavailable():
    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=None):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "development"):
            with patch("edu_cloud.core.token_store.logger") as mock_logger:
                from edu_cloud.core.token_store import is_revoked

                result = await is_revoked("test-jti")

                assert result is False
                mock_logger.warning.assert_called_once()
                assert "fail-open outside production" in str(mock_logger.warning.call_args).lower()


@pytest.mark.asyncio
async def test_is_revoked_fail_closed_in_production_when_redis_unavailable():
    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=None):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "production"):
            with patch("edu_cloud.core.token_store.logger") as mock_logger:
                from edu_cloud.core.token_store import is_revoked

                result = await is_revoked("test-jti")

                assert result is True
                mock_logger.error.assert_called_once()
                assert "fail-closed" in str(mock_logger.error.call_args).lower()


@pytest.mark.asyncio
async def test_is_revoked_fail_closed_in_production_when_redis_errors():
    class BrokenRedis:
        async def exists(self, key):
            raise RuntimeError("redis read failed")

        async def aclose(self):
            return None

    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=BrokenRedis()):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "production"):
            with patch("edu_cloud.core.token_store.logger") as mock_logger:
                from edu_cloud.core.token_store import is_revoked

                result = await is_revoked("test-jti")

                assert result is True
                mock_logger.error.assert_called_once()
                assert "fail-closed" in str(mock_logger.error.call_args).lower()


@pytest.mark.asyncio
async def test_revoke_token_logs_when_redis_unavailable():
    with patch("edu_cloud.core.token_store._get_redis", new_callable=AsyncMock, return_value=None):
        with patch("edu_cloud.core.token_store.logger") as mock_logger:
            from edu_cloud.core.token_store import revoke_token

            result = await revoke_token("test-jti")

            assert result is False
            mock_logger.warning.assert_called_once()
