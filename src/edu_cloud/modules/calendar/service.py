from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.calendar import CalendarEvent, NotificationRule
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError


class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self, type: str, title: str, event_date: date,
        school_id: str, created_by: str,
        semester: str | None = None,
        description: str | None = None,
        notification_rules: list[dict] | None = None,
    ) -> CalendarEvent:
        event = CalendarEvent(
            type=type, title=title, event_date=event_date,
            school_id=school_id, created_by=created_by,
            semester=semester, description=description,
        )
        self.db.add(event)
        await self.db.flush()

        for rule_data in (notification_rules or []):
            rule = NotificationRule(
                event_id=event.id,
                days_before=rule_data["days_before"],
                template_type=rule_data["template_type"],
                target_roles=rule_data["target_roles"],
                auto_draft=rule_data.get("auto_draft", True),
            )
            self.db.add(rule)
        await self.db.commit()
        return event

    async def list_events(
        self, school_id: str, start_date: date | None = None, end_date: date | None = None,
    ) -> list[CalendarEvent]:
        q = select(CalendarEvent).where(
            CalendarEvent.school_id == school_id,
            CalendarEvent.is_active == True,
        )
        if start_date:
            q = q.where(CalendarEvent.event_date >= start_date)
        if end_date:
            q = q.where(CalendarEvent.event_date <= end_date)
        q = q.order_by(CalendarEvent.event_date)
        return list((await self.db.execute(q)).scalars().all())

    async def get_event(self, event_id: str) -> CalendarEvent:
        event = await self.db.get(CalendarEvent, event_id)
        if not event:
            raise NotFoundError(f"Event {event_id} not found")
        return event

    async def delete_event(self, event_id: str, school_id: str | None = None):
        event = await self.get_event(event_id)
        if not school_id:
            raise PermissionDeniedError("School boundary required to delete calendar events")
        if event.school_id != school_id:
            raise PermissionDeniedError("Cannot delete events from other schools")
        event.is_active = False
        await self.db.commit()

    async def get_triggered_rules(self, check_date: date) -> list[dict]:
        """查找 check_date 应触发的通知规则"""
        q = (
            select(NotificationRule, CalendarEvent)
            .join(CalendarEvent, NotificationRule.event_id == CalendarEvent.id)
            .where(
                CalendarEvent.is_active == True,
                NotificationRule.triggered == False,
                NotificationRule.auto_draft == True,
            )
        )
        rows = (await self.db.execute(q)).all()

        triggered = []
        for rule, event in rows:
            trigger_date = event.event_date - timedelta(days=rule.days_before)
            if trigger_date == check_date:
                triggered.append({
                    "rule_id": rule.id,
                    "event_id": event.id,
                    "event_title": event.title,
                    "event_type": event.type,
                    "event_date": str(event.event_date),
                    "template_type": rule.template_type,
                    "target_roles": rule.target_roles,
                    "school_id": event.school_id,
                    "days_before": rule.days_before,
                    "created_by": event.created_by,
                })
        return triggered

    async def mark_rule_triggered(self, rule_id: str):
        rule = await self.db.get(NotificationRule, rule_id)
        if rule:
            rule.triggered = True
            await self.db.commit()
