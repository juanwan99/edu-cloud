"""Tests for edu_cloud.core.tenant module."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from edu_cloud.core.tenant import CROSS_SCHOOL_ROLES, get_school_id


class TestCrossSchoolRoles:
    def test_cross_school_roles_contains_expected(self):
        assert "platform_admin" in CROSS_SCHOOL_ROLES
        assert "district_admin" in CROSS_SCHOOL_ROLES
        assert len(CROSS_SCHOOL_ROLES) == 2

    def test_cross_school_roles_is_frozenset(self):
        assert isinstance(CROSS_SCHOOL_ROLES, frozenset)


class TestGetSchoolId:
    def test_get_school_id_normal_role(self):
        current = {"current_role": SimpleNamespace(role="subject_teacher", school_id="s1")}
        assert get_school_id(current) == "s1"

    def test_get_school_id_admin_returns_none(self):
        for admin_role in ("platform_admin", "district_admin"):
            current = {"current_role": SimpleNamespace(role=admin_role, school_id=None)}
            assert get_school_id(current) is None

    def test_get_school_id_missing_raises_403(self):
        current = {"current_role": SimpleNamespace(role="subject_teacher", school_id=None)}
        with pytest.raises(HTTPException) as exc_info:
            get_school_id(current)
        assert exc_info.value.status_code == 403
