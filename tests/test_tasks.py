import pytest
from datetime import date, timedelta


@pytest.mark.asyncio
async def test_auto_draft_creates_document(db):
    """触发规则匹配后自动创建通知草稿"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    # 创建事件 + 规则
    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试假期", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )

    # 执行自动拟稿
    created_count = await auto_draft_notifications(db, check_date=date.today())
    assert created_count >= 1

    # 验证 Document 已创建
    from edu_cloud.models.document import Document
    from sqlalchemy import select
    docs = (await db.execute(select(Document).where(Document.type == "notification"))).scalars().all()
    assert len(docs) >= 1
    assert "假期" in docs[0].title or "安全" in docs[0].title


@pytest.mark.asyncio
async def test_auto_draft_skips_triggered(db):
    """已触发的规则不重复创建"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )

    count1 = await auto_draft_notifications(db, check_date=date.today())
    count2 = await auto_draft_notifications(db, check_date=date.today())
    assert count1 >= 1
    assert count2 == 0  # 不重复


# ── TG-002: assigned_to 可见性测试 ───────────────────────────────────


@pytest.mark.asyncio
async def test_auto_draft_sets_assigned_to(db):
    """TG-002: 自动拟稿文档的 assigned_to 应设为事件创建者"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications
    from edu_cloud.models.document import Document
    from sqlalchemy import select

    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="测试假期", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
        ],
    )

    await auto_draft_notifications(db, check_date=date.today())

    docs = (await db.execute(select(Document).where(Document.type == "notification"))).scalars().all()
    assert len(docs) >= 1
    doc = docs[0]
    # assigned_to 应与事件创建者一致
    assert doc.assigned_to == "u1"


# ── TG-003: 边界条件测试（tasks 部分）───────────────────────────────


@pytest.mark.asyncio
async def test_auto_draft_unknown_template(db):
    """TG-003: 未知模板跳过不报错"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=3)
    await svc.create_event(
        type="holiday", title="测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 3, "template_type": "nonexistent_template", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    count = await auto_draft_notifications(db, check_date=date.today())
    assert count == 0  # unknown template skipped


@pytest.mark.asyncio
async def test_auto_draft_multiple_rules(db):
    """TG-003: 同一事件多条规则同时触发"""
    from edu_cloud.services.calendar_service import CalendarService
    from edu_cloud.tasks import auto_draft_notifications

    svc = CalendarService(db)
    target_date = date.today() + timedelta(days=7)
    await svc.create_event(
        type="holiday", title="多规则测试", event_date=target_date,
        school_id="s1", created_by="u1",
        notification_rules=[
            {"days_before": 7, "template_type": "holiday_safety", "target_roles": ["parent"], "auto_draft": True},
            {"days_before": 7, "template_type": "exam_reminder", "target_roles": ["parent"], "auto_draft": True},
        ],
    )
    count = await auto_draft_notifications(db, check_date=date.today())
    assert count == 2  # both rules trigger independently
