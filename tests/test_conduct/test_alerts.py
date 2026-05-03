"""Tests for behavior alert system — check_alert_threshold."""
import pytest
from datetime import date

from sqlalchemy import select

from edu_cloud.models.user import User
from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.modules.conduct.models import (
    ConductClassConfig, ConductRecord, ConductNotification,
)
from edu_cloud.modules.conduct.event_service import check_alert_threshold


# ── Helpers ──


async def _make_operator(db):
    operator = User(username="alert_op", display_name="预警老师")
    operator.set_password("123")
    db.add(operator)
    await db.flush()
    return operator


async def _make_parent(db, username, phone, student_id, school_id):
    parent = User(username=username, display_name=username, phone=phone)
    parent.set_password("test123")
    db.add(parent)
    await db.flush()
    link = GuardianStudentLink(
        guardian_user_id=parent.id,
        student_id=student_id,
        relationship="mother",
        is_primary=True,
        school_id=school_id,
    )
    db.add(link)
    await db.commit()
    return parent


async def _add_record(db, student_id, class_id, operator_id, points):
    record = ConductRecord(
        student_id=student_id,
        class_id=class_id,
        points=points,
        reason="测试积分",
        date=date(2026, 5, 1),
        operator_id=operator_id,
    )
    db.add(record)
    await db.commit()
    return record


# ── Tests ──


@pytest.mark.anyio
async def test_alert_below_threshold(db, school_class_student, conduct_config):
    """Set alert_threshold=0. Create records summing to -5. Verify alert created."""
    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = 0
    await db.commit()

    operator = await _make_operator(db)
    parent = await _make_parent(db, "alert_p1", "13800000001", student.id, school.id)

    # Create records summing to -5
    await _add_record(db, student.id, cls.id, operator.id, -3)
    await _add_record(db, student.id, cls.id, operator.id, -2)

    count = await check_alert_threshold(db, student.id, cls.id)
    assert count == 1

    # Verify notification content
    notif = (
        await db.execute(
            select(ConductNotification).where(
                ConductNotification.student_id == student.id,
                ConductNotification.title.like("[预警]%"),
            )
        )
    ).scalar_one()
    assert notif.parent_user_id == parent.id
    assert "[预警]" in notif.title
    assert "张三" in notif.title
    assert notif.record_id is None
    assert notif.is_read is False


@pytest.mark.anyio
async def test_no_alert_above_threshold(db, school_class_student, conduct_config):
    """Set alert_threshold=-10. Create records summing to 5. Returns 0."""
    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = -10
    await db.commit()

    operator = await _make_operator(db)
    await _make_parent(db, "alert_p2", "13800000002", student.id, school.id)

    await _add_record(db, student.id, cls.id, operator.id, 5)

    count = await check_alert_threshold(db, student.id, cls.id)
    assert count == 0


@pytest.mark.anyio
async def test_no_alert_when_disabled(db, school_class_student, conduct_config):
    """alert_threshold=None means alerts disabled. Returns 0 regardless of points."""
    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = None
    await db.commit()

    operator = await _make_operator(db)
    await _make_parent(db, "alert_p3", "13800000003", student.id, school.id)

    await _add_record(db, student.id, cls.id, operator.id, -100)

    count = await check_alert_threshold(db, student.id, cls.id)
    assert count == 0


@pytest.mark.anyio
async def test_no_duplicate_alerts(db, school_class_student, conduct_config):
    """Call check_alert_threshold twice. Second call returns 0 (dedup)."""
    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = 0
    await db.commit()

    operator = await _make_operator(db)
    await _make_parent(db, "alert_p4", "13800000004", student.id, school.id)

    await _add_record(db, student.id, cls.id, operator.id, -5)

    first = await check_alert_threshold(db, student.id, cls.id)
    assert first == 1

    second = await check_alert_threshold(db, student.id, cls.id)
    assert second == 0


@pytest.mark.anyio
async def test_alert_notification_content(db, school_class_student, conduct_config):
    """Verify title format includes student name and current cumulative points."""
    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = 0
    await db.commit()

    operator = await _make_operator(db)
    await _make_parent(db, "alert_p5", "13800000005", student.id, school.id)

    await _add_record(db, student.id, cls.id, operator.id, -3)
    await _add_record(db, student.id, cls.id, operator.id, -4)

    await check_alert_threshold(db, student.id, cls.id)

    notif = (
        await db.execute(
            select(ConductNotification).where(
                ConductNotification.title.like("[预警]%"),
                ConductNotification.student_id == student.id,
            )
        )
    ).scalar_one()

    # Title: [预警] 张三 积分低于预警线（当前 -7，预警线 0）
    assert "张三" in notif.title
    assert "-7" in notif.title
    assert "0" in notif.title
    assert "请关注孩子在校行为表现" in notif.body


@pytest.mark.anyio
async def test_dedup_works_after_mark_all_read(db, school_class_student, conduct_config):
    """F-005: Alert dedup must work even after parent marks all notifications as read.

    Previously, dedup checked is_read==False, so marking alerts as read would
    allow duplicate alerts on the next points change. Now dedup checks for ANY
    alert notification (read or unread) within the 7-day window.
    """
    from sqlalchemy import update

    school, cls, student = school_class_student
    config = conduct_config
    config.alert_threshold = 0
    await db.commit()

    operator = await _make_operator(db)
    await _make_parent(db, "alert_p6", "13800000006", student.id, school.id)

    # Create records below threshold
    await _add_record(db, student.id, cls.id, operator.id, -5)

    # First alert triggers
    first = await check_alert_threshold(db, student.id, cls.id)
    assert first == 1

    # Simulate parent marking all notifications as read
    await db.execute(
        update(ConductNotification)
        .where(ConductNotification.student_id == student.id)
        .values(is_read=True)
    )
    await db.commit()

    # Second call should still dedup (returns 0), even though alerts are now read
    second = await check_alert_threshold(db, student.id, cls.id)
    assert second == 0, (
        "Alert dedup bypassed after mark-all-read: duplicate alert was created"
    )
