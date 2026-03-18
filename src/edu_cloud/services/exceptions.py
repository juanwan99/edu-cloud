"""Service-layer exceptions. Decoupled from FastAPI — no HTTPException here."""


class NotFoundError(Exception):
    """Resource not found."""


class PermissionDeniedError(Exception):
    """Insufficient permissions."""


class ValidationError(Exception):
    """Input validation failed."""


class ConflictError(Exception):
    """Resource conflict (e.g., duplicate)."""


class StateError(Exception):
    """Illegal state transition."""
