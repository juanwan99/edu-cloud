from datetime import date

import pytest
from sqlalchemy import select

from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.calendar.service import CalendarService
from edu_cloud.services.exceptions import PermissionDeniedError


async def _seed_calendar_event(db, seed_teacher, title="Boundary test"):
    role = (
        await db.execute(select(UserRole).where(UserRole.user_id == seed_teacher.id))
    ).scalars().first()
    assert role is not None

    svc = CalendarService(db)
    event = await svc.create_event(
        type="exam",
        title=title,
        event_date=date(2026, 8, 1),
        school_id=role.school_id,
        created_by=seed_teacher.id,
    )
    return svc, event, role.school_id


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
    }, headers=teacher_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_invalid_date_returns_422(client, teacher_headers):
    """R3-2: 非法日期返回 422 而非 500"""
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "holiday", "title": "测试", "event_date": "2026-99-99",
    }, headers=teacher_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_events_invalid_start_returns_422(client, teacher_headers):
    resp = await client.get(
        "/api/v1/calendar/events?start=bad-date",
        headers=teacher_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_events_invalid_end_returns_422(client, teacher_headers):
    resp = await client.get(
        "/api/v1/calendar/events?end=bad-date",
        headers=teacher_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deleted_event_not_in_list(client, teacher_headers):
    """R3-1: 软删除的事件不出现在列表中"""
    resp = await client.post("/api/v1/calendar/events", json={
        "type": "exam", "title": "软删除测试", "event_date": "2026-07-01",
    }, headers=teacher_headers)
    event_id = resp.json()["id"]

    await client.delete(f"/api/v1/calendar/events/{event_id}", headers=teacher_headers)

    list_resp = await client.get("/api/v1/calendar/events", headers=teacher_headers)
    assert list_resp.status_code == 200
    ids = [e["id"] for e in list_resp.json()]
    assert event_id not in ids


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_school_id", [None, ""])
async def test_delete_event_requires_school_boundary(db, seed_teacher, missing_school_id):
    svc, event, _school_id = await _seed_calendar_event(db, seed_teacher)

    with pytest.raises(PermissionDeniedError, match="School boundary required"):
        await svc.delete_event(event.id, school_id=missing_school_id)

    persisted = await svc.get_event(event.id)
    assert persisted.is_active is True


@pytest.mark.asyncio
async def test_delete_event_rejects_other_school(db, seed_teacher):
    svc, event, school_id = await _seed_calendar_event(db, seed_teacher)

    with pytest.raises(PermissionDeniedError, match="other schools"):
        await svc.delete_event(event.id, school_id=f"{school_id}-other")

    persisted = await svc.get_event(event.id)
    assert persisted.is_active is True
