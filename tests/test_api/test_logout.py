"""Logout endpoint tests."""

import pytest
from unittest.mock import AsyncMock, patch

from edu_cloud.api.auth import logout
from edu_cloud.shared.auth import create_access_token


class DummyRequest:
    def __init__(self, token: str):
        self.headers = {"authorization": f"Bearer {token}"}


def _request_with_token() -> DummyRequest:
    token = create_access_token({"sub": "user-1", "jti": "test-jti"})
    return DummyRequest(token)


@pytest.mark.asyncio
async def test_logout_logs_on_revoke_failure_outside_production():
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, side_effect=Exception("Redis down")):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "development"):
            with patch("edu_cloud.core.token_store._environment_is_explicitly_configured", return_value=True):
                with patch("edu_cloud.api.auth.logger") as mock_logger:
                    resp = await logout(_request_with_token(), current={})

                    assert resp["ok"] is True
                    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_logout_returns_503_when_environment_is_defaulted():
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, return_value=False):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "development"):
            with patch("edu_cloud.core.token_store._environment_is_explicitly_configured", return_value=False):
                with pytest.raises(Exception) as exc_info:
                    await logout(_request_with_token(), current={})

                assert exc_info.value.status_code == 503
                assert exc_info.value.detail == "Token revocation unavailable"


@pytest.mark.asyncio
async def test_logout_returns_503_on_revoke_failure_in_production():
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, return_value=False):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "production"):
            with pytest.raises(Exception) as exc_info:
                await logout(_request_with_token(), current={})

            assert exc_info.value.status_code == 503
            assert exc_info.value.detail == "Token revocation unavailable"


@pytest.mark.asyncio
async def test_logout_raises_503_on_revoke_exception_in_production():
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, side_effect=Exception("Redis down")):
        with patch("edu_cloud.core.token_store.settings.ENVIRONMENT", "production"):
            with patch("edu_cloud.api.auth.logger") as mock_logger:
                with pytest.raises(Exception) as exc_info:
                    await logout(_request_with_token(), current={})

                assert exc_info.value.status_code == 503
                assert exc_info.value.detail == "Token revocation unavailable"
                mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_logout_success():
    with patch("edu_cloud.core.token_store.revoke_token", new_callable=AsyncMock, return_value=True):
        resp = await logout(_request_with_token(), current={})

    assert resp["ok"] is True
