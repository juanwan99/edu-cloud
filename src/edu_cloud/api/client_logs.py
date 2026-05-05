"""POST /api/v1/client-logs — receives frontend error/event batches."""

import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from edu_cloud.logging_config import log_event

router = APIRouter(prefix="/api/v1", tags=["client-logs"])
logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: {client_session_id: (count, window_start)}
_rate_counters: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
_RATE_LIMIT = 100  # max events per session per minute
_RATE_WINDOW = 60.0  # seconds


class ClientEvent(BaseModel):
    ts: str
    level: str
    event_type: str
    page_route: str = ""
    trace_id: str = ""
    data: dict = Field(default_factory=dict)


class ClientLogPayload(BaseModel):
    client_session_id: str
    build_id: Optional[str] = None
    events: list[ClientEvent] = Field(default_factory=list, max_length=50)


@router.post("/client-logs", status_code=204, response_class=Response)
async def receive_client_logs(payload: ClientLogPayload, request: Request):
    """Accept a batch of client-side log events."""
    session_id = payload.client_session_id

    # Rate limiting
    now = time.monotonic()
    count, window_start = _rate_counters[session_id]
    if now - window_start > _RATE_WINDOW:
        count = 0
        window_start = now
    if count + len(payload.events) > _RATE_LIMIT:
        return Response(status_code=429)
    _rate_counters[session_id] = (count + len(payload.events), window_start)

    # Best-effort user/school extraction from JWT (sendBeacon may be anonymous)
    user_id = None
    school_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from edu_cloud.shared.auth import decode_token
            token_payload = decode_token(auth_header[7:])
            user_id = token_payload.get("sub")
            school_id = token_payload.get("school_id")
        except Exception:
            pass

    # Log each event
    for ev in payload.events:
        log_event(
            "edu_cloud.client",
            logging.WARNING if ev.level == "error" else logging.INFO,
            layer="client",
            event=ev.event_type,
            msg=f"[client] {ev.event_type} on {ev.page_route}",
            client_session_id=session_id,
            build_id=payload.build_id,
            client_ts=ev.ts,
            client_level=ev.level,
            page_route=ev.page_route,
            trace_id=ev.trace_id,
            user_id=user_id,
            school_id=school_id,
            client_data=ev.data,
        )

    return Response(status_code=204)
