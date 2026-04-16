"""Request ID propagation tests (adapted from exam-ai trace_id tests).

edu-cloud uses X-Request-ID (not X-Trace-ID). Tests adapted accordingly.
"""
import pytest


async def test_auto_generate_request_id(client):
    """When no X-Request-ID header, middleware should auto-generate one."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    request_id = resp.headers.get("X-Request-ID")
    assert request_id is not None
    assert len(request_id) == 12


async def test_echo_request_id(client):
    """X-Request-ID sent by client should be echoed back."""
    resp = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "req-test-456"},
    )
    assert resp.headers["X-Request-ID"] == "req-test-456"


async def test_response_always_has_request_id(client):
    """Response should always include X-Request-ID header."""
    resp = await client.get("/api/v1/health")
    assert "X-Request-ID" in resp.headers


async def test_error_path_includes_request_id(client):
    """Unhandled exception path should also return X-Request-ID."""
    from fastapi import APIRouter

    crash_router = APIRouter()

    @crash_router.get("/api/v1/_test_crash")
    async def _crash():
        raise RuntimeError("deliberate crash for request-id test")

    app = client._transport.app
    app.include_router(crash_router)

    resp = await client.get(
        "/api/v1/_test_crash",
        headers={"X-Request-ID": "crash-req-001"},
    )
    assert resp.status_code == 500
    assert resp.headers["X-Request-ID"] == "crash-req-001"
