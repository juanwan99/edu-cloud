import pytest
from edu_cloud.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_dispatch_stub(db):
    """stub 模式下标记为 sent"""
    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc1",
        target_scope={"class_ids": ["c1"]},
        school_id="s1",
        channel="stub",
    )
    assert result["status"] == "sent"
    assert result["channel"] == "stub"


@pytest.mark.asyncio
async def test_dispatch_idempotent(db):
    """同一 document_id 不重复发送"""
    svc = NotificationService(db)
    r1 = await svc.dispatch(document_id="doc1", target_scope={}, school_id="s1", channel="stub")
    r2 = await svc.dispatch(document_id="doc1", target_scope={}, school_id="s1", channel="stub")
    assert r1["status"] == "sent"
    assert r2["status"] == "already_sent"  # 幂等


# ── TG-003: 边界条件测试 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_non_stub_channel(db):
    """TG-003: 非 stub 渠道标记为 pending"""
    svc = NotificationService(db)
    result = await svc.dispatch(
        document_id="doc_wechat",
        target_scope={"class_ids": ["c1"]},
        school_id="s1",
        channel="wechat",
    )
    assert result["status"] == "pending"
