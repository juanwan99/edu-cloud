"""Portal aggregation DTO schemas."""
from __future__ import annotations

from pydantic import BaseModel


class TodoItem(BaseModel):
    id: str
    source_module: str
    source_type: str
    source_id: str
    title: str
    summary: str | None = None
    status: str
    priority: str
    school_id: str
    assignee_scope: dict
    due_at: str | None = None
    created_at: str
    updated_at: str
    action_url: str
    permission: str
    module_code: str


class MessageItem(BaseModel):
    id: str
    source_module: str
    source_type: str
    source_id: str
    kind: str
    title: str
    summary: str | None = None
    severity: str
    read: bool
    created_at: str
    action_url: str
    permission: str
    module_code: str


class CalendarDigestItem(BaseModel):
    id: str
    source_module: str
    source_id: str
    event_date: str
    title: str
    type: str
    school_id: str
    action_url: str
    module_code: str


class ServiceEntry(BaseModel):
    id: str
    module_code: str
    title: str
    description: str
    route: str
    permission: str
    enabled: bool
    badge_source: str | None = None


class PortalSummary(BaseModel):
    role: str
    school_id: str | None
    todo_count: int
    unread_message_count: int
    calendar_count: int
    service_count: int
    enabled_modules: list[str]

