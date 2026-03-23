from edu_cloud.models.base import Base, TenantMixin


def test_tenant_mixin_has_school_id():
    assert hasattr(TenantMixin, "school_id")


def test_base_has_metadata():
    assert hasattr(Base, "metadata")
