import pytest


@pytest.mark.asyncio
async def test_create_event(client, teacher_headers):
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "holiday", "title": "五一放假",
        "event_date": "2026-05-01",
        "notification_rules": [
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True}
        ],
    }, headers=teacher_headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == "五一放假"


@pytest.mark.asyncio
async def test_list_events(client, teacher_headers):
    await client.post("/api/v1/calendar/events", json={
        "type": "exam", "title": "期中考试", "event_date": "2026-04-20",
    }, headers=teacher_headers)
    resp = await client.get("/api/v1/calendar/events", headers=teacher_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_delete_event(client, teacher_headers):
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "exam", "title": "删除测试", "event_date": "2026-06-01",
    }, headers=teacher_headers)
    event_id = resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=teacher_headers)
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_calendar_requires_auth(client):
    resp = await client.get("/api/v1/calendar/events")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_event_missing_field_returns_422(client, teacher_headers):
    """CB-4: 缺少必填字段返回 422"""
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "holiday",
        # missing title and event_date
    }, headers=teacher_headers)
    assert resp.status_code == 422
