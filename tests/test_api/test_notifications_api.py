"""Notifications List API 测试。"""
import pytest
from datetime import datetime, timedelta, timezone


@pytest.fixture
async def seed_notifications(db):
    """Seed 4 条通知：2 pending(校A) + 1 sent(校A) + 1 pending(校B)。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.notification import Notification
    from edu_cloud.models.document import Document
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    school_a = School(name="通知校A", code="NOTIA", district="测试区", api_key_hash="x")
    school_b = School(name="通知校B", code="NOTIB", district="测试区", api_key_hash="x")
    db.add_all([school_a, school_b])
    await db.flush()

    user = User(username="noti_seed", display_name="种子用户")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))

    doc_a = Document(type="notification", title="通知A", status="executed",
                     school_id=school_a.id, created_by=user.id)
    doc_b = Document(type="notification", title="通知B", status="executed",
                     school_id=school_b.id, created_by=user.id)
    db.add_all([doc_a, doc_b])
    await db.flush()

    now = datetime.now(timezone.utc)
    n1 = Notification(document_id=doc_a.id, school_id=school_a.id, status="pending",
                      channel="system", created_at=now - timedelta(hours=1))
    n2 = Notification(document_id=doc_a.id, school_id=school_a.id, status="pending",
                      channel="wechat", created_at=now - timedelta(days=10))
    n3 = Notification(document_id=doc_a.id, school_id=school_a.id, status="sent",
                      channel="system", created_at=now - timedelta(hours=2))
    n4 = Notification(document_id=doc_b.id, school_id=school_b.id, status="pending",
                      channel="system", created_at=now)
    db.add_all([n1, n2, n3, n4])
    await db.commit()
    return {"school_a_id": school_a.id, "school_b_id": school_b.id}


@pytest.mark.asyncio
async def test_notifications_list_school_scope(client, db, seed_notifications):
    """教师只看到本校通知（3 条），不看他校（1 条）。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    school_a_id = seed_notifications["school_a_id"]
    user = User(username="noti_teacher", display_name="通知教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher",
                    school_id=school_a_id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login",
                              json={"username": "noti_teacher", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # CR-02: 字段语义断言
    for item in data:
        assert "title" in item and item["title"]  # 非空
        assert item["kind"] in ("system", "message", "approval")
        assert isinstance(item["unread"], bool)
    # title 来自 Document.title（非占位串）
    titles = {item["title"] for item in data}
    assert "通知A" in titles  # seed 的 doc_a.title


@pytest.mark.asyncio
async def test_notifications_filter_status_pending(client, db, seed_notifications):
    """status=pending 只返回 pending 通知。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = User(username="noti_filter", display_name="过滤测试")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher",
                    school_id=seed_notifications["school_a_id"], is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login",
                              json={"username": "noti_filter", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications?status=pending", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    # CR-02: unread 只对 pending 为真
    assert all(n["unread"] is True for n in resp.json())


@pytest.mark.asyncio
async def test_notifications_filter_since_week(client, db, seed_notifications):
    """since=week 排除 10 天前的通知。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = User(username="noti_since", display_name="时间过滤测试")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher",
                    school_id=seed_notifications["school_a_id"], is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login",
                              json={"username": "noti_since", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications?since=week", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_notifications_unauth(client):
    """未认证 → 401。"""
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code in (401, 403)
