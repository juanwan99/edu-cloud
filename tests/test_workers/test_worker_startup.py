"""worker 启动检查测试"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_worker_startup_calls_startup_checks():
    """worker 启动应调用 run_startup_checks"""
    with patch("edu_cloud.startup_checks.run_startup_checks", new_callable=AsyncMock) as mock_checks:
        with patch("edu_cloud.logging_config.setup_logging"):
            from edu_cloud.worker import on_worker_startup
            await on_worker_startup({})
            mock_checks.assert_called_once()


@pytest.mark.asyncio
async def test_worker_startup_skips_with_env(monkeypatch):
    """SKIP_STARTUP_CHECKS=1 时 worker 应正常启动"""
    monkeypatch.setenv("SKIP_STARTUP_CHECKS", "1")
    with patch("edu_cloud.logging_config.setup_logging"):
        from edu_cloud.worker import on_worker_startup
        await on_worker_startup({})
