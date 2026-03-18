import pytest


@pytest.mark.asyncio
async def test_admin_has_manage_schools(client, admin_headers):
    """platform_admin can access school management endpoints."""
    resp = await client.get("/api/v1/schools", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_without_token(client):
    """No token → 403 (HTTPBearer returns 403)."""
    resp = await client.get("/api/v1/schools")
    assert resp.status_code == 403
