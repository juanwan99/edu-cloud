"""Logging system contract tests (GPT F011).

Verifies:
- _JSONLFormatter extracts custom record attributes to top-level JSON fields
- Request logging middleware generates/echoes trace_id
- ContextVars reset between requests
- business_event() writes to the correct logger with correct layer
- Client logs endpoint rate limiting
"""

import json
import logging
import re
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from edu_cloud.logging_config import (
    _JSONLFormatter,
    business_event,
    trace_id_var,
)


# --------------------------------------------------------------------------
# Test 1: _JSONLFormatter extracts _layer, _event, _data at top level
# --------------------------------------------------------------------------

def test_jsonl_formatter_extracts_layer_event_data():
    formatter = _JSONLFormatter()
    logger = logging.getLogger("test.contract.layer")
    record = logger.makeRecord(
        "test.contract.layer", logging.INFO,
        "(test)", 0, "test message", (), None,
    )
    record._layer = "business"
    record._event = "entity.created"
    record._data = {"entity_id": "abc123", "action": "create"}

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["layer"] == "business"
    assert parsed["event"] == "entity.created"
    assert parsed["data"]["entity_id"] == "abc123"
    assert parsed["data"]["action"] == "create"


# --------------------------------------------------------------------------
# Test 2: _JSONLFormatter extracts _duration_ms
# --------------------------------------------------------------------------

def test_jsonl_formatter_extracts_duration():
    formatter = _JSONLFormatter()
    logger = logging.getLogger("test.contract.duration")
    record = logger.makeRecord(
        "test.contract.duration", logging.INFO,
        "(test)", 0, "timed op", (), None,
    )
    record._duration_ms = 123

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["duration_ms"] == 123


# --------------------------------------------------------------------------
# Test 3: Middleware generates trace_id with tr_ + 12 hex pattern
# --------------------------------------------------------------------------

@pytest.mark.anyio
async def test_middleware_generates_trace_id(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200

    trace_id = resp.headers.get("X-Trace-ID")
    assert trace_id is not None
    assert re.match(r"^tr_[0-9a-f]{12}$", trace_id)


# --------------------------------------------------------------------------
# Test 4: Middleware echoes provided trace_id unchanged
# --------------------------------------------------------------------------

@pytest.mark.anyio
async def test_middleware_echoes_provided_trace_id(client):
    custom_trace = "tr_custom123abc"
    resp = await client.get(
        "/api/v1/health",
        headers={"X-Trace-ID": custom_trace},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Trace-ID") == custom_trace


# --------------------------------------------------------------------------
# Test 5: ContextVars reset after request (trace_id isolation)
# --------------------------------------------------------------------------

@pytest.mark.anyio
async def test_context_vars_reset_after_request(client):
    # First request with a specific trace_id
    resp1 = await client.get(
        "/api/v1/health",
        headers={"X-Trace-ID": "tr_first_request"},
    )
    assert resp1.headers.get("X-Trace-ID") == "tr_first_request"

    # Second request without specifying trace_id
    resp2 = await client.get("/api/v1/health")
    trace2 = resp2.headers.get("X-Trace-ID")

    # Second request must NOT inherit first request's trace_id
    assert trace2 != "tr_first_request"
    assert re.match(r"^tr_[0-9a-f]{12}$", trace2)


# --------------------------------------------------------------------------
# Test 6: business_event() writes to logger with _layer="business"
# --------------------------------------------------------------------------

def test_business_event_writes_to_both_loggers():
    with patch("logging.Logger.handle") as mock_handle:
        business_event(
            "score_update", "exam_result", "res-001",
            old_state="80", new_state="85",
        )

        # business_event calls logger.handle — find the record
        assert mock_handle.called
        record = mock_handle.call_args[0][0]
        assert record._layer == "business"
        assert record._event == "business.score_update"
        assert record._data["entity_type"] == "exam_result"
        assert record._data["entity_id"] == "res-001"
        assert record._data["old_state"] == "80"
        assert record._data["new_state"] == "85"


# --------------------------------------------------------------------------
# Test 7: Client logs endpoint rate limit (>100 events → 429)
# --------------------------------------------------------------------------

@pytest.mark.anyio
async def test_client_logs_endpoint_rate_limit(client):
    # Reset rate limiter state by using a unique session id
    session_id = "rate_limit_test_session_unique_001"

    # Build a payload exceeding the 100-events-per-minute limit
    # The endpoint accepts max 50 events per request, so we need 3 calls
    events = [
        {"ts": "2026-05-05T10:00:00+08:00", "level": "info",
         "event_type": "user_action", "page_route": "/test"}
        for _ in range(50)
    ]

    # First batch: 50 events (total: 50, under limit)
    resp1 = await client.post("/api/v1/client-logs", json={
        "client_session_id": session_id,
        "events": events,
    })
    assert resp1.status_code == 204

    # Second batch: 50 events (total: 100, at limit)
    resp2 = await client.post("/api/v1/client-logs", json={
        "client_session_id": session_id,
        "events": events,
    })
    assert resp2.status_code == 204

    # Third batch: should exceed limit and return 429
    resp3 = await client.post("/api/v1/client-logs", json={
        "client_session_id": session_id,
        "events": [events[0]],  # even 1 event should trigger
    })
    assert resp3.status_code == 429


