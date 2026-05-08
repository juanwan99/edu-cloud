"""N-H08: login rate limit (5/minute per IP) via slowapi."""

import pytest


@pytest.mark.asyncio
async def test_login_rate_limit_triggers(client):
    """6 consecutive wrong logins from same IP should trigger 429."""
    for i in range(6):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": f"attacker{i}", "password": "wrong"},
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_login_within_limit_works(client):
    """A single login attempt should not trigger rate limit."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code != 429
