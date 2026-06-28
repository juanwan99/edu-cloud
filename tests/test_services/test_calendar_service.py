import pytest
from datetime import date, timedelta
from edu_cloud.services.calendar_service import CalendarService


@pytest.mark.asyncio
async def test_create_event(db):
    svc = CalendarService(db)
    event = await svc.create_event(
        type="holiday", title="五一放假", event_date=date(2026, 5, 1),
        school_id="s1", created_by="u1", semester="2025-2026-2",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
            {"days_before": 1, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    assert event.title == "五一放假"
    assert event.type == "holiday"


@pytest.mark.asyncio
async def test_list_events(db):
    svc = CalendarService(db)
    await svc.create_event(
        type="exam", title="期中考试", event_date=date(2026, 4, 20),
        school_id="s1", created_by="u1",
    )
    events = await svc.list_events(school_id="s1")
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_get_triggered_rules(db):
    """查找今天应触发的规则"""
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试假期", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules) >= 1
    assert rules[0]["template_type"] == "holiday_safety"
    assert rules[0]["created_by"] == "u1"  # F1 fix: 确认 created_by 从事件传递


@pytest.mark.asyncio
async def test_triggered_rule_not_repeated(db):
    """已触发的规则不重复"""
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules1 = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules1) >= 1
    # 标记已触发
    await svc.mark_rule_triggered(rules1[0]["rule_id"])
    rules2 = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules2) == 0


@pytest.mark.asyncio
async def test_delete_event(db):
    svc = CalendarService(db)
    event = await svc.create_event(
        type="exam", title="删除测试", event_date=date(2026, 6, 1),
        school_id="s1", created_by="u1",
    )
    await svc.delete_event(event.id, school_id="s1")
    events = await svc.list_events(school_id="s1")
    active = [e for e in events if e.is_active]
    assert len(active) == 0


# ── TG-003: 边界条件测试 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_days_before_zero_triggers_same_day(db):
    """TG-003: days_before=0 当天触发"""
    svc = CalendarService(db)
    await svc.create_event(
        type="exam", title="今天考试", event_date=date.today(),
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 0, "template_type": "exam_reminder", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_past_event_not_triggered(db):
    """TG-003: 过期事件不触发"""
    svc = CalendarService(db)
    await svc.create_event(
        type="holiday", title="过去的假期", event_date=date(2020, 1, 1),
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    rules = await svc.get_triggered_rules(check_date=date.today())
    assert len(rules) == 0
