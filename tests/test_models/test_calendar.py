# tests/test_models/test_calendar.py
from edu_cloud.models.calendar import CalendarEvent, NotificationRule
from edu_cloud.models.notification import Notification

def test_calendar_event_fields():
    cols = {c.name for c in CalendarEvent.__table__.columns}
    assert "type" in cols          # holiday / exam / parent_meeting / deadline
    assert "title" in cols
    assert "event_date" in cols
    assert "school_id" in cols
    assert "created_by" in cols

def test_calendar_event_defaults():
    e = CalendarEvent(type="holiday", title="五一放假", school_id="s1", created_by="u1")
    assert e.is_active is True

def test_notification_rule_fields():
    cols = {c.name for c in NotificationRule.__table__.columns}
    assert "event_id" in cols
    assert "days_before" in cols
    assert "template_type" in cols
    assert "target_roles" in cols
    assert "auto_draft" in cols

def test_notification_fields():
    cols = {c.name for c in Notification.__table__.columns}
    assert "document_id" in cols
    assert "channel" in cols
    assert "status" in cols
    assert "target_scope" in cols
    assert "result_summary" in cols

def test_notification_default_status():
    n = Notification(document_id="d1", channel="wechat", school_id="s1")
    assert n.status == "pending"
