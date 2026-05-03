"""Tests for conduct notification system — event_service + notification_router."""
import pytest
from datetime import date

from edu_cloud.models.user import User
from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.conduct.models import ConductRecord, ConductNotification, StudentProfile
from edu_cloud.modules.conduct.event_service import notify_parents_on_points
from edu_cloud.modules.conduct.crypto import encrypt


# ── Helper ──

async def _make_parent_user(db, username, phone):
    """Create a parent user (User row, no UserRole needed for service tests)."""
    user = User(username=username, display_name=username, phone=phone)
    user.set_password("test123")
    db.add(user)
    await db.flush()
    return user


async def _bind_parent(db, parent_user_id, student_id, school_id, relationship="mother"):
    """Create a GuardianStudentLink."""
    link = GuardianStudentLink(
        guardian_user_id=parent_user_id,
        student_id=student_id,
        relationship=relationship,
        is_primary=True,
        school_id=school_id,
    )
    db.add(link)
    await db.commit()
    return link


async def _make_record(db, student_id, class_id, operator_id, points=5, reason="课堂表现好"):
    """Create a ConductRecord."""
    record = ConductRecord(
        student_id=student_id,
        class_id=class_id,
        points=points,
        reason=reason,
        date=date(2026, 5, 1),
        operator_id=operator_id,
    )
    db.add(record)
    await db.commit()
    return record


# ── Service-level tests ──


@pytest.mark.anyio
async def test_notify_creates_notification(db, school_class_student):
    """Create record + parent binding, call notify, verify notification in DB."""
    school, cls, student = school_class_student

    # Create operator + parent
    operator = User(username="op_notify", display_name="通知老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    parent = await _make_parent_user(db, "notify_parent", "13900000001")
    await _bind_parent(db, parent.id, student.id, school.id)

    record = await _make_record(db, student.id, cls.id, operator.id, points=5, reason="表现优秀")

    count = await notify_parents_on_points(db, record.id)
    assert count == 1

    # Verify notification exists
    from sqlalchemy import select
    notif = (
        await db.execute(
            select(ConductNotification).where(ConductNotification.record_id == record.id)
        )
    ).scalar_one()
    assert notif.parent_user_id == parent.id
    assert notif.student_id == student.id
    assert notif.is_read is False
    assert "张三" in notif.title
    assert "+5" in notif.title
    assert "表现优秀" in notif.body


@pytest.mark.anyio
async def test_notify_no_binding(db, school_class_student):
    """No parent binding -> returns 0, no notifications created."""
    school, cls, student = school_class_student

    operator = User(username="op_no_bind", display_name="无绑定老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    record = await _make_record(db, student.id, cls.id, operator.id)

    count = await notify_parents_on_points(db, record.id)
    assert count == 0


@pytest.mark.anyio
async def test_notify_multiple_parents(db, school_class_student):
    """Bind 2 parents to same student, verify 2 notifications created."""
    school, cls, student = school_class_student

    operator = User(username="op_multi", display_name="多家长老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    parent1 = await _make_parent_user(db, "parent_m1", "13900000010")
    parent2 = await _make_parent_user(db, "parent_m2", "13900000011")
    await _bind_parent(db, parent1.id, student.id, school.id, "mother")
    await _bind_parent(db, parent2.id, student.id, school.id, "father")

    record = await _make_record(db, student.id, cls.id, operator.id, points=-3, reason="上课说话")

    count = await notify_parents_on_points(db, record.id)
    assert count == 2

    # Verify both parents got notifications
    from sqlalchemy import select
    notifs = (
        await db.execute(
            select(ConductNotification).where(ConductNotification.record_id == record.id)
        )
    ).scalars().all()
    parent_ids = {n.parent_user_id for n in notifs}
    assert parent_ids == {parent1.id, parent2.id}


@pytest.mark.anyio
async def test_notification_content_format(db, school_class_student):
    """Verify title contains student name and point value, body contains reason and date."""
    school, cls, student = school_class_student

    operator = User(username="op_fmt", display_name="格式老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    parent = await _make_parent_user(db, "fmt_parent", "13900000020")
    await _bind_parent(db, parent.id, student.id, school.id)

    # Positive points
    record_pos = await _make_record(db, student.id, cls.id, operator.id, points=10, reason="积极参与")
    await notify_parents_on_points(db, record_pos.id)

    from sqlalchemy import select
    notif_pos = (
        await db.execute(
            select(ConductNotification).where(ConductNotification.record_id == record_pos.id)
        )
    ).scalar_one()
    assert "张三" in notif_pos.title
    assert "+10" in notif_pos.title
    assert "积极参与" in notif_pos.body
    assert "2026-05-01" in notif_pos.body

    # Negative points
    record_neg = await _make_record(db, student.id, cls.id, operator.id, points=-2, reason="迟到")
    await notify_parents_on_points(db, record_neg.id)

    notif_neg = (
        await db.execute(
            select(ConductNotification).where(ConductNotification.record_id == record_neg.id)
        )
    ).scalar_one()
    assert "-2" in notif_neg.title
    assert "迟到" in notif_neg.body


# ── HTTP endpoint tests ──


async def _register_and_bind_parent(client, db, school_class_student, phone, name="测试家长"):
    """Register parent via API, bind to student, return headers."""
    school, cls, student = school_class_student

    # Ensure conduct config exists
    from edu_cloud.modules.conduct.models import ConductClassConfig
    from sqlalchemy import select
    existing_config = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == cls.id)
        )
    ).scalar_one_or_none()
    if not existing_config:
        config = ConductClassConfig(class_id=cls.id, invite_code="NTFY01", verify_code_type="custom")
        db.add(config)
        await db.flush()

    # Ensure student profile with verify code
    existing_profile = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.student_id == student.id)
        )
    ).scalar_one_or_none()
    if not existing_profile:
        profile = StudentProfile(student_id=student.id, verify_code=encrypt("BIND99"))
        db.add(profile)
    await db.commit()

    # Determine invite code from config
    config_row = (
        await db.execute(
            select(ConductClassConfig).where(ConductClassConfig.class_id == cls.id)
        )
    ).scalar_one()
    invite_code = config_row.invite_code

    # Register
    resp = await client.post("/api/v1/conduct/parent/register", json={
        "invite_code": invite_code,
        "display_name": name,
        "phone": phone,
        "password": "abc123",
    })
    assert resp.status_code == 200, f"register failed: {resp.json()}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Bind
    resp = await client.post("/api/v1/conduct/parent/bind", headers=headers, json={
        "class_id": cls.id,
        "student_name": "张三",
        "verify_code": "BIND99",
    })
    assert resp.status_code == 200, f"bind failed: {resp.json()}"

    return headers, student


@pytest.mark.anyio
async def test_get_notifications_endpoint(client, db, school_class_student):
    """HTTP test: GET /parent/notifications returns notification list."""
    school, cls, student = school_class_student

    headers, student = await _register_and_bind_parent(
        client, db, school_class_student, "13900000030",
    )

    # Create operator and a conduct record manually
    operator = User(username="op_http1", display_name="HTTP老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    record = ConductRecord(
        student_id=student.id,
        class_id=cls.id,
        points=8,
        reason="作业优秀",
        date=date(2026, 5, 2),
        operator_id=operator.id,
    )
    db.add(record)
    await db.commit()

    # Trigger notification via service
    count = await notify_parents_on_points(db, record.id)
    assert count == 1

    # GET notifications
    resp = await client.get("/api/v1/conduct/parent/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] is not None
    assert "+8" in data[0]["title"]
    assert data[0]["is_read"] is False
    assert data[0]["student_id"] == student.id

    # Test unread_only filter
    resp = await client.get(
        "/api/v1/conduct/parent/notifications?unread_only=true", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.anyio
async def test_mark_all_read(client, db, school_class_student):
    """HTTP test: POST /parent/notifications/read-all marks all as read."""
    school, cls, student = school_class_student

    headers, student = await _register_and_bind_parent(
        client, db, school_class_student, "13900000031", name="已读家长",
    )

    # Create operator and 2 conduct records
    operator = User(username="op_http2", display_name="已读老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()

    for pts, reason in [(3, "积极发言"), (-1, "作业忘交")]:
        record = ConductRecord(
            student_id=student.id,
            class_id=cls.id,
            points=pts,
            reason=reason,
            date=date(2026, 5, 2),
            operator_id=operator.id,
        )
        db.add(record)
        await db.commit()
        await notify_parents_on_points(db, record.id)

    # Verify 2 unread notifications
    resp = await client.get(
        "/api/v1/conduct/parent/notifications?unread_only=true", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Mark all as read
    resp = await client.post(
        "/api/v1/conduct/parent/notifications/read-all", headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Verify no unread notifications remain
    resp = await client.get(
        "/api/v1/conduct/parent/notifications?unread_only=true", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # But all notifications still exist
    resp = await client.get(
        "/api/v1/conduct/parent/notifications", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert all(n["is_read"] for n in resp.json())
