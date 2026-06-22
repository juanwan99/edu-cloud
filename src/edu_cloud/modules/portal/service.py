"""Portal aggregation service.

This module composes source services into stable portal DTOs. It intentionally
does not import source table models; source modules keep table ownership.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.permissions import Permission
from edu_cloud.models.school_settings import MODULE_CODES
from edu_cloud.services.portal_workflow import CalendarService, HomeworkTaskService
from edu_cloud.services.school_settings_service import get_enabled_modules


SERVICE_CATALOG: tuple[dict[str, str | None], ...] = (
    {
        "id": "exam",
        "module_code": "exam",
        "title": "考试管理",
        "description": "考试、科目、题目与成绩入口",
        "route": "/exams",
        "permission": Permission.VIEW_EXAMS.value,
        "badge_source": "todo",
    },
    {
        "id": "grading",
        "module_code": "grading",
        "title": "阅卷系统",
        "description": "阅卷任务、质量检查与结果确认",
        "route": "/grading",
        "permission": Permission.VIEW_GRADING.value,
        "badge_source": "todo",
    },
    {
        "id": "homework",
        "module_code": "homework",
        "title": "作业管理",
        "description": "作业布置、提交批改与补救练习",
        "route": "/homework",
        "permission": Permission.VIEW_HOMEWORK.value,
        "badge_source": "todo",
    },
    {
        "id": "study_analytics",
        "module_code": "study_analytics",
        "title": "学情分析",
        "description": "班级、学生、知识点分析",
        "route": "/analytics",
        "permission": Permission.VIEW_SCORES.value,
        "badge_source": None,
    },
    {
        "id": "research",
        "module_code": "research",
        "title": "教研题库",
        "description": "题库、错题本与知识图谱",
        "route": "/knowledge-tree",
        "permission": Permission.VIEW_KNOWLEDGE_TREE.value,
        "badge_source": None,
    },
    {
        "id": "teaching",
        "module_code": "teaching",
        "title": "教学管理",
        "description": "排课、选科与教学安排",
        "route": "/academic",
        "permission": Permission.MANAGE_SCHEDULING.value,
        "badge_source": None,
    },
    {
        "id": "calendar",
        "module_code": "calendar",
        "title": "校历日程",
        "description": "校历、提醒与日程安排",
        "route": "/calendar",
        "permission": Permission.GENERATE_NOTIFICATION.value,
        "badge_source": "calendar",
    },
    {
        "id": "studio",
        "module_code": "studio",
        "title": "文档中心",
        "description": "通知、报告与审批文档",
        "route": "/studio",
        "permission": Permission.GENERATE_REPORT.value,
        "badge_source": "message",
    },
    {
        "id": "conduct",
        "module_code": "conduct",
        "title": "德育管理",
        "description": "操行积分、班规与家长通知",
        "route": "/conduct",
        "permission": Permission.VIEW_CONDUCT.value,
        "badge_source": "message",
    },
)


def _role(current: dict) -> Any:
    return current["current_role"]


def _school_id(current: dict) -> str | None:
    return getattr(_role(current), "school_id", None)


def _role_name(current: dict) -> str:
    return getattr(_role(current), "role", "")


def _permission_values(current: dict) -> set[str]:
    raw = current.get("permissions") or set()
    return {item.value if hasattr(item, "value") else str(item) for item in raw}


def _has_permission(current: dict, permission: str) -> bool:
    return permission in _permission_values(current)


async def enabled_module_codes(db: AsyncSession, current: dict) -> set[str]:
    school_id = _school_id(current)
    if not school_id:
        return set(MODULE_CODES)
    return await get_enabled_modules(db, school_id=school_id)


def _scope_payload(current: dict) -> dict:
    role = _role(current)
    return {
        "role": getattr(role, "role", None),
        "role_id": getattr(role, "id", None),
        "class_ids": getattr(role, "class_ids", None),
        "grade_ids": getattr(role, "grade_ids", None),
        "subject_codes": getattr(role, "subject_codes", None),
    }


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class PortalAggregationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_services(self, current: dict) -> list[dict]:
        enabled = await enabled_module_codes(self.db, current)
        entries: list[dict] = []
        for item in SERVICE_CATALOG:
            is_enabled = str(item["module_code"]) in enabled
            permission = str(item["permission"])
            if not is_enabled or not _has_permission(current, permission):
                continue
            entries.append({**item, "enabled": is_enabled})
        return entries

    async def list_todos(self, current: dict) -> list[dict]:
        school_id = _school_id(current)
        enabled = await enabled_module_codes(self.db, current)
        if (
            not school_id
            or "homework" not in enabled
            or not _has_permission(current, Permission.VIEW_HOMEWORK.value)
        ):
            return []

        role = _role(current)
        assigned_by = None
        if getattr(role, "role", "") == "subject_teacher":
            assigned_by = current["user"].id
        class_id = None
        if getattr(role, "role", "") == "homeroom_teacher":
            class_ids = getattr(role, "class_ids", None) or []
            if len(class_ids) == 1:
                class_id = class_ids[0]

        tasks = await HomeworkTaskService.list_tasks(
            self.db,
            school_id=school_id,
            class_id=class_id,
            status="active",
            assigned_by=assigned_by,
        )
        return [self._homework_todo(current, task) for task in tasks[:10]]

    def _homework_todo(self, current: dict, task) -> dict:
        created = _iso(getattr(task, "created_at", None)) or ""
        updated = _iso(getattr(task, "updated_at", None)) or created
        due_at = _iso(getattr(task, "deadline", None))
        priority = "high" if due_at and due_at < date.today().isoformat() else "normal"
        return {
            "id": f"homework:{task.id}",
            "source_module": "homework",
            "source_type": "homework_task",
            "source_id": task.id,
            "title": task.title,
            "summary": f"{task.subject_code} · {task.task_type}",
            "status": "open",
            "priority": priority,
            "school_id": task.school_id,
            "assignee_scope": _scope_payload(current),
            "due_at": due_at,
            "created_at": created,
            "updated_at": updated,
            "action_url": f"/homework?taskId={task.id}",
            "permission": Permission.VIEW_HOMEWORK.value,
            "module_code": "homework",
        }

    async def list_messages(self, current: dict) -> list[dict]:
        school_id = _school_id(current)
        enabled = await enabled_module_codes(self.db, current)
        if (
            not school_id
            or "studio" not in enabled
            or not _has_permission(current, Permission.GENERATE_REPORT.value)
        ):
            return []

        from edu_cloud.api.notifications_api import list_notifications

        rows = await list_notifications(
            status=None, since="week", current=current, db=self.db
        )
        return [self._notification_message(row) for row in rows[:10]]

    def _notification_message(self, row: dict) -> dict:
        kind = row.get("kind") or "notification"
        unread = bool(row.get("unread"))
        return {
            "id": f"notification:{row['id']}",
            "source_module": "studio",
            "source_type": "notification",
            "source_id": row["id"],
            "kind": kind,
            "title": row.get("title") or "通知",
            "summary": row.get("summary"),
            "severity": "warning" if unread else "info",
            "read": not unread,
            "created_at": str(row.get("created_at") or ""),
            "action_url": "/studio",
            "permission": Permission.GENERATE_REPORT.value,
            "module_code": "studio",
        }

    async def list_calendar_digest(self, current: dict) -> list[dict]:
        school_id = _school_id(current)
        enabled = await enabled_module_codes(self.db, current)
        if (
            not school_id
            or "calendar" not in enabled
            or not _has_permission(current, Permission.GENERATE_NOTIFICATION.value)
        ):
            return []

        today = date.today()
        events = await CalendarService(self.db).list_events(
            school_id=school_id,
            start_date=today,
            end_date=today + timedelta(days=14),
        )
        return [
            {
                "id": f"calendar:{event.id}",
                "source_module": "calendar",
                "source_id": event.id,
                "event_date": str(event.event_date),
                "title": event.title,
                "type": event.type,
                "school_id": event.school_id,
                "action_url": f"/calendar?eventId={event.id}",
                "module_code": "calendar",
            }
            for event in events[:10]
        ]

    async def summary(self, current: dict) -> dict:
        enabled = sorted(await enabled_module_codes(self.db, current))
        todos = await self.list_todos(current)
        messages = await self.list_messages(current)
        calendar = await self.list_calendar_digest(current)
        services = await self.list_services(current)
        return {
            "role": _role_name(current),
            "school_id": _school_id(current),
            "todo_count": len(todos),
            "unread_message_count": sum(1 for item in messages if not item["read"]),
            "calendar_count": len(calendar),
            "service_count": len(services),
            "enabled_modules": enabled,
        }
