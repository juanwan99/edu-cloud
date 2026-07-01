import pytest
from sqlalchemy import select

from edu_cloud.models.notification import Notification
from edu_cloud.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_dispatch_stub(db):
    """stub dispatch is recorded as not sent."""
    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc1",
        target_scope={"class_ids": ["c1"]},
        school_id="s1",
        channel="stub",
    )

    assert result["status"] == "pending"
    assert result["channel"] == "stub"
    assert result["sent"] is False
    assert result["delivery_state"] == "not_configured"
    assert result["result"]["dry_run"] is True
    assert result["result"]["success"] == 0

    notification = await db.get(Notification, result["notification_id"])
    assert notification.status == "pending"
    assert notification.sent_at is None
    assert notification.result_summary["sent"] is False


@pytest.mark.asyncio
async def test_dispatch_idempotent(db):
    """Repeated stub dispatch reuses the pending record without claiming sent."""
    svc = NotificationService(db)
    r1 = await svc.dispatch(
        document_id="doc1",
        target_scope={},
        school_id="s1",
        channel="stub",
    )
    r2 = await svc.dispatch(
        document_id="doc1",
        target_scope={},
        school_id="s1",
        channel="stub",
    )

    assert r1["status"] == "pending"
    assert r2["status"] == "pending"
    assert r2["sent"] is False
    assert r2["notification_id"] == r1["notification_id"]

    notifications = (await db.execute(
        select(Notification).where(Notification.document_id == "doc1")
    )).scalars().all()
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_dispatch_legacy_stub_sent_record_does_not_report_sent(db):
    """Legacy stub rows marked sent are not treated as real delivery evidence."""
    existing = Notification(
        document_id="doc_legacy",
        target_scope={},
        school_id="s1",
        channel="stub",
        status="sent",
    )
    db.add(existing)
    await db.flush()

    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc_legacy",
        target_scope={},
        school_id="s1",
        channel="stub",
    )

    assert result["status"] == "pending"
    assert result["sent"] is False
    assert result["delivery_state"] == "not_configured"
    assert result["result"]["legacy_status"] == "sent"


@pytest.mark.asyncio
async def test_dispatch_non_stub_ignores_legacy_stub_sent_record(db):
    """Legacy stub rows do not block a later real-channel dispatch request."""
    existing = Notification(
        document_id="doc_legacy_provider",
        target_scope={},
        school_id="s1",
        channel="stub",
        status="sent",
    )
    db.add(existing)
    await db.flush()

    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc_legacy_provider",
        target_scope={},
        school_id="s1",
        channel="wechat",
    )

    assert result["status"] == "pending"
    assert result["channel"] == "wechat"
    assert result["sent"] is False
    assert result["delivery_state"] == "pending_provider"
    assert result["notification_id"] != existing.id

    notifications = (await db.execute(
        select(Notification).where(Notification.document_id == "doc_legacy_provider")
    )).scalars().all()
    assert len(notifications) == 2


@pytest.mark.asyncio
async def test_dispatch_non_stub_channel(db):
    """Non-stub channels remain pending until a provider actually sends."""
    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc_wechat",
        target_scope={"class_ids": ["c1"]},
        school_id="s1",
        channel="wechat",
    )

    assert result["status"] == "pending"
    assert result["sent"] is False
    assert result["delivery_state"] == "pending_provider"
    assert result["result"]["sent"] is False
