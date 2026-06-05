from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from edu_cloud.core.permissions import ROLE_PERMISSIONS
from edu_cloud.models.document import Document
from edu_cloud.models.notification import Notification
from edu_cloud.models.school import School
from edu_cloud.models.school_settings import SchoolModule
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.calendar.service import CalendarService
from edu_cloud.modules.homework.service import HomeworkTaskService
from edu_cloud.modules.portal.service import PortalAggregationService
from edu_cloud.shared.auth import create_access_token
from edu_cloud.api.router_registry import MODULE_ROUTERS

pytestmark = pytest.mark.asyncio


async def _seed_identity(db, role_name: str = "academic_director"):
    school = School(name="Portal Test School", code="PORTAL01", district="测试区", api_key_hash="x")
    user = User(username=f"{role_name}_user", display_name="Portal User")
    user.set_password("test123")
    db.add_all([school, user])
    await db.flush()
    role = UserRole(user_id=user.id, role=role_name, school_id=school.id, is_primary=True)
    db.add(role)
    await db.flush()
    return school, user, role


async def _enable(db, school_id: str, *codes: str):
    for code in codes:
        db.add(SchoolModule(school_id=school_id, module_code=code, enabled=True))
    await db.flush()


def _current(user, role):
    return {
        "user": user,
        "current_role": role,
        "permissions": ROLE_PERMISSIONS[role.role],
    }


async def test_portal_services_filter_by_module_switch_and_permission(db):
    school, user, role = await _seed_identity(db)
    await _enable(db, school.id, "homework", "calendar", "studio")
    current = _current(user, role)

    services = await PortalAggregationService(db).list_services(current)
    codes = {item["module_code"] for item in services}

    assert "homework" in codes
    assert "calendar" in codes
    assert "studio" in codes
    assert "conduct" not in codes
    assert all(item["enabled"] is True for item in services)


async def test_portal_todos_emit_contract_shape_from_homework_service(db):
    school, user, role = await _seed_identity(db)
    await _enable(db, school.id, "homework")
    task = await HomeworkTaskService.create_task(
        db,
        school_id=school.id,
        title="完成函数练习",
        task_type="regular",
        subject_code="math",
        class_id=None,
        assigned_by=user.id,
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
    )
    task.status = "active"
    await db.commit()

    todos = await PortalAggregationService(db).list_todos(_current(user, role))

    assert len(todos) == 1
    item = todos[0]
    assert item["id"] == f"homework:{task.id}"
    assert item["source_module"] == "homework"
    assert item["source_type"] == "homework_task"
    assert item["source_id"] == task.id
    assert item["action_url"] == f"/homework?taskId={task.id}"
    assert item["permission"] == "view_homework"
    assert item["module_code"] == "homework"
    assert item["assignee_scope"]["role"] == "academic_director"


async def test_portal_calendar_digest_uses_calendar_service(db):
    school, user, role = await _seed_identity(db)
    await _enable(db, school.id, "calendar")
    event = await CalendarService(db).create_event(
        type="exam",
        title="期中考试",
        event_date=date.today() + timedelta(days=2),
        school_id=school.id,
        created_by=user.id,
    )

    digest = await PortalAggregationService(db).list_calendar_digest(_current(user, role))

    assert digest == [
        {
            "id": f"calendar:{event.id}",
            "source_module": "calendar",
            "source_id": event.id,
            "event_date": str(event.event_date),
            "title": "期中考试",
            "type": "exam",
            "school_id": school.id,
            "action_url": f"/calendar?eventId={event.id}",
            "module_code": "calendar",
        }
    ]


async def test_portal_messages_normalize_existing_notifications_api(db):
    school, user, role = await _seed_identity(db)
    await _enable(db, school.id, "studio")
    doc = Document(
        type="notification",
        title="家长会通知",
        created_by=user.id,
        school_id=school.id,
    )
    db.add(doc)
    await db.flush()
    db.add(Notification(document_id=doc.id, school_id=school.id, status="pending"))
    await db.commit()

    messages = await PortalAggregationService(db).list_messages(_current(user, role))

    assert len(messages) == 1
    assert messages[0]["source_module"] == "studio"
    assert messages[0]["source_type"] == "notification"
    assert messages[0]["kind"] == "message"
    assert messages[0]["title"] == "家长会通知"
    assert messages[0]["read"] is False
    assert messages[0]["module_code"] == "studio"


async def test_schoolless_role_does_not_scan_school_scoped_sources(db):
    user = SimpleNamespace(id="u-platform")
    role = SimpleNamespace(
        id="r-platform",
        role="platform_admin",
        school_id=None,
        class_ids=None,
        grade_ids=None,
        subject_codes=None,
    )
    current = {
        "user": user,
        "current_role": role,
        "permissions": ROLE_PERMISSIONS["platform_admin"],
    }
    service = PortalAggregationService(db)

    assert await service.list_todos(current) == []
    assert await service.list_messages(current) == []
    assert await service.list_calendar_digest(current) == []


async def test_portal_router_is_registered():
    assert ("edu_cloud.modules.portal.router", "router") in MODULE_ROUTERS


async def test_portal_services_endpoint_is_registered(client, db):
    school, user, role = await _seed_identity(db)
    await _enable(db, school.id, "homework")
    await db.commit()
    token = create_access_token({
        "sub": user.id,
        "role": role.role,
        "active_role_id": role.id,
    })

    response = await client.get(
        "/api/v1/portal/services",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["module_code"] for item in payload] == ["homework"]
    assert payload[0]["permission"] == "view_homework"
