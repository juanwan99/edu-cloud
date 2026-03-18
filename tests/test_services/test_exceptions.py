import pytest
from edu_cloud.services.exceptions import (
    NotFoundError, PermissionDeniedError, ValidationError,
    ConflictError, StateError,
)


def test_exception_classes_exist():
    """All 5 custom exceptions are importable and are Exception subclasses."""
    for cls in [NotFoundError, PermissionDeniedError, ValidationError, ConflictError, StateError]:
        assert issubclass(cls, Exception)
        exc = cls("test message")
        assert str(exc) == "test message"


def test_exception_empty_message():
    """Empty message returns empty detail."""
    exc = NotFoundError("")
    assert str(exc) == ""


@pytest.mark.asyncio
async def test_not_found_returns_404(client):
    """Global handler maps NotFoundError → 404."""
    resp = await client.get(
        "/api/v1/schools/nonexistent-id",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404
