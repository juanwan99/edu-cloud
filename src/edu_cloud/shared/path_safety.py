"""Shared path safety functions for file access boundaries.

Two distinct entry points:
- resolve_user_input_path: for paths from HTTP request bodies (user-supplied)
- resolve_stored_file_path: for paths from database (e.g. StudentAnswer.image_path)

These MUST NOT be conflated — stored paths like ./storage/... resolve relative
to the project root, while user-input paths resolve relative to UPLOAD_DIR.
"""

from pathlib import Path

from fastapi import HTTPException

from edu_cloud.config import settings

# Project root: directory containing src/, storage/, uploads/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _get_allowed_roots() -> list[Path]:
    return [
        (_PROJECT_ROOT / settings.UPLOAD_DIR).resolve(),
        (_PROJECT_ROOT / settings.STORAGE_ROOT).resolve(),
    ]


def resolve_user_input_path(
    p: str | Path,
    *,
    allowed_roots: list[Path] | None = None,
) -> Path:
    """Resolve a user-supplied path (from request body) and verify containment.

    Relative paths are resolved against UPLOAD_DIR (default root for user input).
    Raises HTTP 403 if path escapes allowed roots.
    """
    roots = [r.resolve() for r in (allowed_roots or _get_allowed_roots())]
    default_root = roots[0]  # UPLOAD_DIR

    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = default_root / candidate
    resolved = candidate.resolve()

    if not any(resolved == r or resolved.is_relative_to(r) for r in roots):
        raise HTTPException(403, "路径不在允许的根目录范围内")
    return resolved


def resolve_stored_file_path(
    p: str | Path,
    *,
    allowed_roots: list[Path] | None = None,
) -> Path:
    """Resolve a database-stored path (e.g. StudentAnswer.image_path).

    Relative paths like ./storage/... are resolved against the PROJECT ROOT,
    not UPLOAD_DIR. This preserves compatibility with existing data.
    Raises HTTP 403 if path escapes allowed roots.
    """
    roots = [r.resolve() for r in (allowed_roots or _get_allowed_roots())]

    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = _PROJECT_ROOT / candidate
    resolved = candidate.resolve()

    if not any(resolved == r or resolved.is_relative_to(r) for r in roots):
        raise HTTPException(403, "文件路径不在允许范围内")
    return resolved
