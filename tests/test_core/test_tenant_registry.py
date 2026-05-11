"""Tests for the tenant isolation registry (audit mode)."""
import pytest


class TestTenantContextVar:
    """ContextVar-based tenant state management."""

    def test_default_is_none(self):
        from edu_cloud.core.tenant_registry import get_tenant
        # In a fresh context, tenant should be None
        assert get_tenant() is None

    def test_set_and_get(self):
        from edu_cloud.core.tenant_registry import set_tenant, get_tenant, clear_tenant
        set_tenant("school-abc")
        assert get_tenant() == "school-abc"
        clear_tenant()
        assert get_tenant() is None

    def test_overwrite(self):
        from edu_cloud.core.tenant_registry import set_tenant, get_tenant, clear_tenant
        set_tenant("school-1")
        set_tenant("school-2")
        assert get_tenant() == "school-2"
        clear_tenant()

    def test_clear_is_idempotent(self):
        from edu_cloud.core.tenant_registry import clear_tenant, get_tenant
        clear_tenant()
        clear_tenant()
        assert get_tenant() is None

    def test_set_none_clears(self):
        from edu_cloud.core.tenant_registry import set_tenant, get_tenant
        set_tenant("school-x")
        set_tenant(None)
        assert get_tenant() is None


class TestTenantScopedModels:
    """Auto-discovery of tenant-scoped models."""

    def test_discovers_tenant_mixin_models(self):
        """Models inheriting TenantMixin should be discovered."""
        from edu_cloud.core.tenant_registry import get_tenant_scoped_models, _reset_cache
        _reset_cache()
        scoped = get_tenant_scoped_models()
        # GuardianStudentLink uses TenantMixin explicitly
        assert "guardian_student_links" in scoped

    def test_discovers_module_models_with_school_id(self):
        """Module models that define school_id directly (not via TenantMixin)."""
        from edu_cloud.core.tenant_registry import get_tenant_scoped_models, _reset_cache
        _reset_cache()
        scoped = get_tenant_scoped_models()
        # Exam model has school_id but doesn't inherit TenantMixin
        assert "exams" in scoped

    def test_cache_returns_same_set(self):
        """Second call should return the cached set."""
        from edu_cloud.core.tenant_registry import get_tenant_scoped_models, _reset_cache
        _reset_cache()
        first = get_tenant_scoped_models()
        second = get_tenant_scoped_models()
        assert first is second  # same object, not just equal

    def test_non_tenant_tables_excluded(self):
        """Tables without school_id should not appear."""
        from edu_cloud.core.tenant_registry import get_tenant_scoped_models, _reset_cache
        _reset_cache()
        scoped = get_tenant_scoped_models()
        # 'users' table has no school_id column
        assert "users" not in scoped

    def test_minimum_count(self):
        """Sanity check: there should be a meaningful number of scoped tables."""
        from edu_cloud.core.tenant_registry import get_tenant_scoped_models, _reset_cache
        _reset_cache()
        scoped = get_tenant_scoped_models()
        # The codebase has 30+ models with school_id
        assert len(scoped) >= 15


class TestTenantMode:
    """TENANT_MODE configuration."""

    def test_default_mode_is_audit(self):
        from edu_cloud.core.tenant_registry import TENANT_MODE
        assert TENANT_MODE == "audit"
