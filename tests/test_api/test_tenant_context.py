import pytest
from sqlalchemy import select
from edu_cloud.core.tenant import TenantContext


def _mock_ctx(school_id="s1", subject_codes=None, class_ids=None):
    return TenantContext(
        user_id="u1", role_id="r1", role_name="subject_teacher",
        school_id=school_id,
        visible_class_ids=class_ids,
        visible_subject_codes=subject_codes,
    )


def test_require_school_returns_id():
    ctx = _mock_ctx(school_id="school-1")
    assert ctx.require_school() == "school-1"


def test_require_school_raises_for_admin():
    ctx = _mock_ctx(school_id=None)
    with pytest.raises(Exception) as exc_info:
        ctx.require_school()
    assert exc_info.value.status_code == 403


def test_apply_subject_scope_none_no_filter():
    ctx = _mock_ctx(subject_codes=None)
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "IN" not in compiled


def test_apply_subject_scope_empty_tuple_deny_all():
    ctx = _mock_ctx(subject_codes=())
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "1 != 1" in compiled or "false" in compiled.lower() or "IN (NULL)" in compiled


def test_apply_subject_scope_with_values():
    ctx = _mock_ctx(subject_codes=("math", "chinese"))
    from edu_cloud.modules.exam.models import Subject
    stmt = select(Subject)
    result = ctx.apply_subject_scope(stmt, Subject.code)
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "IN" in compiled


def test_get_tenant_context_admin():
    from edu_cloud.api.deps import get_tenant_context
    from unittest.mock import MagicMock
    role = MagicMock()
    role.role = "platform_admin"
    role.school_id = None
    role.id = "role-1"
    role.class_ids = None
    role.subject_codes = None
    user = MagicMock()
    user.id = "admin-1"
    current = {"user": user, "current_role": role}
    import asyncio
    ctx = asyncio.run(get_tenant_context(current))
    assert ctx.school_id is None
    assert ctx.visible_class_ids is None
    assert ctx.visible_subject_codes is None


def test_get_tenant_context_teacher():
    from edu_cloud.api.deps import get_tenant_context
    from unittest.mock import MagicMock
    role = MagicMock()
    role.role = "subject_teacher"
    role.school_id = "school-1"
    role.id = "role-2"
    role.class_ids = ["c1", "c2"]
    role.subject_codes = ["math"]
    user = MagicMock()
    user.id = "teacher-1"
    current = {"user": user, "current_role": role}
    import asyncio
    ctx = asyncio.run(get_tenant_context(current))
    assert ctx.school_id == "school-1"
    assert ctx.visible_class_ids == ("c1", "c2")
    assert ctx.visible_subject_codes == ("math",)
