"""worker ??????"""
import json
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_worker_startup_calls_startup_checks(monkeypatch, tmp_path):
    """worker ????? run_startup_checks???? runtime fingerprint?"""
    state_path = tmp_path / "worker-runtime.json"
    monkeypatch.setenv("EDU_CLOUD_WORKER_RUNTIME_STATE", str(state_path))
    with patch("edu_cloud.startup_checks.run_startup_checks", new_callable=AsyncMock) as mock_checks:
        with patch("edu_cloud.logging_config.setup_logging"):
            from edu_cloud.worker import on_worker_startup
            await on_worker_startup({})
            mock_checks.assert_called_once()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "edu-cloud.worker-runtime.v1"
    assert payload["process"] == "worker"
    assert isinstance(payload["pid"], int)
    assert "boot_time" in payload
    assert "git_hash" in payload
    assert isinstance(payload["source_dirty"], bool)


@pytest.mark.asyncio
async def test_worker_startup_skips_with_env(monkeypatch, tmp_path):
    """SKIP_STARTUP_CHECKS=1 ? worker ????????? runtime fingerprint?"""
    state_path = tmp_path / "worker-runtime.json"
    monkeypatch.setenv("SKIP_STARTUP_CHECKS", "1")
    monkeypatch.setenv("EDU_CLOUD_WORKER_RUNTIME_STATE", str(state_path))
    with patch("edu_cloud.logging_config.setup_logging"):
        from edu_cloud.worker import on_worker_startup
        await on_worker_startup({})
    assert json.loads(state_path.read_text(encoding="utf-8"))["service"] == "edu-cloud-worker"
