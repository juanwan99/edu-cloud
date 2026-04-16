import pytest


@pytest.mark.asyncio
async def test_create_school_api(client, admin_headers):
    resp = await client.post("/api/v1/schools", json={
        "name": "API测试校", "code": "API01", "district": "测试区",
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "API01"
    assert "api_key" in data  # plaintext key returned once


@pytest.mark.asyncio
async def test_list_schools_api(client, admin_headers):
    # Create 2 schools
    await client.post("/api/v1/schools", json={
        "name": "A校", "code": "LSA", "district": "X区",
    }, headers=admin_headers)
    await client.post("/api/v1/schools", json={
        "name": "B校", "code": "LSB", "district": "Y区",
    }, headers=admin_headers)
    # List all
    resp = await client.get("/api/v1/schools", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2
    # Filter by district
    resp = await client.get("/api/v1/schools?district=X区", headers=admin_headers)
    assert all(s["district"] == "X区" for s in resp.json())


@pytest.mark.asyncio
async def test_get_school_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "详情校", "code": "DET01", "district": "Z区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/schools/{school_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == "DET01"


@pytest.mark.asyncio
async def test_update_school_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "更新校", "code": "UPD01", "district": "W区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/schools/{school_id}", json={
        "is_active": False,
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_rotate_key_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "轮换校", "code": "ROT01", "district": "V区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/schools/{school_id}/rotate-key", headers=admin_headers)
    assert resp.status_code == 200
    assert "api_key" in resp.json()


@pytest.mark.asyncio
async def test_get_nonexistent_school_404(client, admin_headers):
    resp = await client.get("/api/v1/schools/nonexistent", headers=admin_headers)
    assert resp.status_code == 404
