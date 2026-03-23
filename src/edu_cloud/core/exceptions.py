# Re-export from services.exceptions — canonical location stays at services/
# until Task 22 consolidation
from edu_cloud.services.exceptions import (  # noqa: F401
    NotFoundError, PermissionDeniedError, ValidationError, ConflictError, StateError,
)
