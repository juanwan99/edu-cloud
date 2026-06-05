"""Tests for backend/frontend permission mirror governance."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "governance"))

from check_permission_mirror import (  # noqa: E402
    check_repo,
    parse_frontend_mirror,
)


def test_permission_mirror_is_clean_for_repo():
    assert check_repo(PROJECT_ROOT) == []


def test_parse_frontend_mirror_resolves_teacher_base_expressions(tmp_path):
    config = tmp_path / "frontend/src/config"
    config.mkdir(parents=True)
    (config / "permissions.js").write_text(
        """
        const _TEACHER_BASE = ['view_students', 'view_conduct', 'manage_conduct']

        export const ROLE_PERMISSIONS = {
          platform_admin: ['view_students', 'manage_platform'],
          lesson_prep_leader: _TEACHER_BASE
            .filter(p => p !== 'view_conduct' && p !== 'manage_conduct')
            .concat('manage_exams'),
          homeroom_teacher: [..._TEACHER_BASE, 'send_notification'],
          subject_teacher: [..._TEACHER_BASE],
        }
        """,
        encoding="utf-8",
    )
    (config / "roles.js").write_text(
        """
        export const CANONICAL_ROLES = [
          'platform_admin', 'lesson_prep_leader',
          'homeroom_teacher', 'subject_teacher',
        ]
        export const LEGACY_ALIAS_MAP = {
          teacher: 'subject_teacher',
          head_teacher: 'homeroom_teacher',
        }
        """,
        encoding="utf-8",
    )

    mirror = parse_frontend_mirror(tmp_path)

    assert mirror.role_permissions["lesson_prep_leader"] == {
        "view_students",
        "manage_exams",
    }
    assert mirror.role_permissions["homeroom_teacher"] == {
        "view_students",
        "view_conduct",
        "manage_conduct",
        "send_notification",
    }
    assert mirror.legacy_aliases["teacher"] == "subject_teacher"
