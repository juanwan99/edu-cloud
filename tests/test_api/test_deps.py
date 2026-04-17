import pytest


@pytest.mark.asyncio
async def test_admin_has_manage_schools(client, admin_headers):
    """platform_admin can access school management endpoints."""
    resp = await client.get("/api/v1/schools", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_without_token(client):
    """No token → 401（deps.py 显式 raise 401，auto_error=False）。"""
    resp = await client.get("/api/v1/schools")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_observer_cannot_create_school(client, observer_headers):
    """observer 角色无 MANAGE_SCHOOLS 权限 → 403。"""
    resp = await client.post("/api/v1/schools", json={
        "name": "X", "code": "X01", "district": "X",
    }, headers=observer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_observer_cannot_update_school(client, admin_headers, observer_headers):
    """observer 角色无法更新学校 → 403。"""
    # Create school as admin
    cr = await client.post("/api/v1/schools", json={
        "name": "Y", "code": "Y01", "district": "Y",
    }, headers=admin_headers)
    school_id = cr.json()["id"]
    # Observer tries to update → 403
    resp = await client.patch(f"/api/v1/schools/{school_id}", json={
        "is_active": False,
    }, headers=observer_headers)
    assert resp.status_code == 403
