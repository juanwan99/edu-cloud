"""进程内事件总线：模块间解耦通信。

使用方式：
    from edu_cloud.core.events import event_bus

    # 订阅
    @event_bus.on("grading.completed")
    async def handle_grading_completed(payload):
        ...

    # 发布
    await event_bus.emit("grading.completed", {"exam_id": "...", "school_id": "..."})
"""

import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event: str):
        """Decorator to register an event handler."""
        def decorator(fn: EventHandler) -> EventHandler:
            self._handlers[event].append(fn)
            logger.debug("event_bus: registered handler %s for '%s'", fn.__name__, event)
            return fn
        return decorator

    async def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Emit an event, calling all registered handlers."""
        handlers = self._handlers.get(event, [])
        if not handlers:
            logger.debug("event_bus: no handlers for '%s'", event)
            return

        payload = payload or {}
        logger.info("event_bus: emitting '%s' to %d handler(s)", event, len(handlers))
        for handler in handlers:
            try:
                await handler(payload)
            except Exception:
                logger.error(
                    "event_bus: handler %s failed for '%s'",
                    handler.__name__, event, exc_info=True,
                )


event_bus = EventBus()
