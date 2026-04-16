"""Integration tests for DataScope + IntentRouter in api/ai.py + worker cron registration."""

import pytest


@pytest.mark.asyncio
async def test_ai_chat_no_auth_returns_401(client):
    resp = await client.post("/api/v1/ai/chat", json={"message": "test"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_health(client):
    resp = await client.get("/api/v1/ai/health")
    assert resp.status_code == 200
    assert resp.json()["tools"] > 0


def test_worker_has_w3_w6_cron():
    from edu_cloud.worker import WorkerSettings

    job_funcs = [j.coroutine.__name__ for j in WorkerSettings.cron_jobs]
    assert "run_w3_daily" in job_funcs
    assert "run_w6_hourly" in job_funcs


def test_worker_functions_include_crons():
    from edu_cloud.worker import WorkerSettings

    func_names = [f.__name__ for f in WorkerSettings.functions]
    assert "run_w3_daily" in func_names
    assert "run_w6_hourly" in func_names
