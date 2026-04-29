import re

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "edu-cloud"


@pytest.mark.asyncio
async def test_version(client):
    resp = await client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "boot_time" in data
    assert "git_hash" in data
    assert re.match(r'^[0-9a-f]{7,}$|^unknown$', data["git_hash"])
    assert "source_dirty" in data
    assert isinstance(data["source_dirty"], bool)
    assert "pid" in data
    assert isinstance(data["pid"], int)
    assert data["pid"] > 0
