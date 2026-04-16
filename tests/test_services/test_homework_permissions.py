import pytest
from edu_cloud.core.permissions import Permission, has_permission


def test_manage_homework_permission():
    """MANAGE_HOMEWORK 对教师角色可用。"""
    assert has_permission("subject_teacher", Permission.MANAGE_HOMEWORK)
    assert has_permission("homeroom_teacher", Permission.MANAGE_HOMEWORK)
    assert has_permission("platform_admin", Permission.MANAGE_HOMEWORK)
    assert not has_permission("parent", Permission.MANAGE_HOMEWORK)
    assert not has_permission("grade_leader", Permission.MANAGE_HOMEWORK)


def test_view_homework_permission():
    """VIEW_HOMEWORK 对所有教学角色可用，包括 parent 和 grade_leader。"""
    assert has_permission("subject_teacher", Permission.VIEW_HOMEWORK)
    assert has_permission("homeroom_teacher", Permission.VIEW_HOMEWORK)
    assert has_permission("grade_leader", Permission.VIEW_HOMEWORK)
    assert has_permission("parent", Permission.VIEW_HOMEWORK)
    assert not has_permission("observer", Permission.VIEW_HOMEWORK)


def test_homework_in_module_codes():
    """homework 模块已注册。"""
    from edu_cloud.models.school_settings import MODULE_CODES, DEFAULT_ENABLED
    assert "homework" in MODULE_CODES
    assert "homework" in DEFAULT_ENABLED


@pytest.mark.asyncio
async def test_homework_capability_defaults(db):
    """init_school_capabilities 包含 homework 域。"""
    from edu_cloud.models.school import School
    from edu_cloud.services.capability_service import init_school_capabilities, get_capabilities

    school = School(name="Cap测试校", code="CAP01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()

    await init_school_capabilities(db, school_id=school.id)
    caps = await get_capabilities(db, school_id=school.id)

    hw_caps = [c for c in caps if c.domain == "homework"]
    assert len(hw_caps) > 0

    # subject_teacher 有 homework read+write
    st_hw = [c for c in hw_caps if c.role == "subject_teacher"]
    assert any(c.action == "read" and c.enabled for c in st_hw)
    assert any(c.action == "write" and c.enabled for c in st_hw)

    # grade_leader 只有 homework read
    gl_hw = [c for c in hw_caps if c.role == "grade_leader"]
    assert any(c.action == "read" and c.enabled for c in gl_hw)
    gl_write = [c for c in gl_hw if c.action == "write"]
    assert not gl_write or not any(c.enabled for c in gl_write)
