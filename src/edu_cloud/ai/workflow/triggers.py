"""Event-to-workflow trigger — connects EventBus events to WorkflowExecutor."""
from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from edu_cloud.core.events import EventBus

logger = logging.getLogger(__name__)

ExecutorFunc = Callable[..., Coroutine[Any, Any, Any]]


class EventTrigger:
    """Register EventBus events that automatically launch workflows."""

    def __init__(self, bus: EventBus, executor_func: ExecutorFunc) -> None:
        self._bus = bus
        self._execute = executor_func

    def register(self, event: str, workflow_name: str) -> None:
        @self._bus.on(event)
        async def handler(payload: dict) -> None:
            trigger_ref = payload.get("exam_id") or payload.get("id", "")
            school_id = payload.get("school_id", "")
            logger.info(
                "EventTrigger: '%s' → workflow '%s' (ref=%s, school=%s)",
                event, workflow_name, trigger_ref, school_id,
            )
            await self._execute(
                workflow_name=workflow_name,
                school_id=school_id,
                trigger_type="event",
                trigger_ref=trigger_ref,
            )
