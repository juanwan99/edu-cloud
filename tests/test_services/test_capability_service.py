import pytest
from edu_cloud.models.capability import Capability, CAPABILITY_DOMAINS, CAPABILITY_ACTIONS


@pytest.mark.asyncio
async def test_capability_domains_contains_nine():
    assert len(CAPABILITY_DOMAINS) == 9
    assert "exam" in CAPABILITY_DOMAINS
    assert "system" in CAPABILITY_DOMAINS


@pytest.mark.asyncio
async def test_capability_actions():
    assert CAPABILITY_ACTIONS == {"read", "write"}


@pytest.mark.asyncio
async def test_capability_model(db, seed_school):
    school, _ = seed_school
    cap = Capability(
        school_id=school.id,
        role="principal",
        domain="exam",
        action="read",
        enabled=True,
    )
    db.add(cap)
    await db.commit()
    await db.refresh(cap)
    assert cap.id is not None
    assert cap.role == "principal"
    assert cap.domain == "exam"
    assert cap.action == "read"
    assert cap.enabled is True


@pytest.mark.asyncio
async def test_capability_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError

    school, _ = seed_school
    c1 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=True)
    c2 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=False)
    db.add(c1)
    await db.flush()
    db.add(c2)
    with pytest.raises(IntegrityError):
        await db.flush()


# ── Service tests ──

from edu_cloud.services.capability_service import (
    init_school_capabilities, get_capabilities, set_capability, check_capability,
    DEFAULT_CAPABILITIES,
)


@pytest.mark.asyncio
async def test_default_capabilities_template():
    """DEFAULT_CAPABILITIES 包含 6 个角色模板。"""
    assert "principal" in DEFAULT_CAPABILITIES
    assert "academic_director" in DEFAULT_CAPABILITIES
    assert "grade_leader" in DEFAULT_CAPABILITIES
    assert "homeroom_teacher" in DEFAULT_CAPABILITIES
    assert "subject_teacher" in DEFAULT_CAPABILITIES
    assert "parent" in DEFAULT_CAPABILITIES
    assert "platform_admin" not in DEFAULT_CAPABILITIES
    assert "district_admin" not in DEFAULT_CAPABILITIES


@pytest.mark.asyncio
async def test_init_school_capabilities(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    caps = await get_capabilities(db, school_id=school.id)
    assert len(caps) > 0
    principal_caps = [c for c in caps if c.role == "principal"]
    assert len(principal_caps) == 18  # 9 domains × 2 actions
    assert all(c.enabled for c in principal_caps)


@pytest.mark.asyncio
async def test_init_school_capabilities_idempotent(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    count1 = len(await get_capabilities(db, school_id=school.id))
    await init_school_capabilities(db, school_id=school.id)
    count2 = len(await get_capabilities(db, school_id=school.id))
    assert count1 == count2


@pytest.mark.asyncio
async def test_get_capabilities_filter_by_role(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    parent_caps = await get_capabilities(db, school_id=school.id, role="parent")
    assert len(parent_caps) == 1
    assert parent_caps[0].domain == "study_analytics"
    assert parent_caps[0].action == "read"


@pytest.mark.asyncio
async def test_set_capability(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    cap = await set_capability(
        db, school_id=school.id, role="principal",
        domain="exam", action="write", enabled=False,
    )
    assert cap.enabled is False
    result = await check_capability(
        db, school_id=school.id, role="principal", domain="exam", action="write",
    )
    assert result is False


@pytest.mark.asyncio
async def test_check_capability_no_record_default_allow(db, seed_school):
    """无记录 = 默认允许（宽松策略）。"""
    school, _ = seed_school
    result = await check_capability(
        db, school_id=school.id, role="principal", domain="exam", action="read",
    )
    assert result is True


@pytest.mark.asyncio
async def test_check_capability_explicit_false(db, seed_school):
    """显式 enabled=False → 拒绝。"""
    school, _ = seed_school
    await set_capability(
        db, school_id=school.id, role="subject_teacher",
        domain="system", action="write", enabled=False,
    )
    result = await check_capability(
        db, school_id=school.id, role="subject_teacher", domain="system", action="write",
    )
    assert result is False


@pytest.mark.asyncio
async def test_set_capability_invalid_domain(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError

    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的域"):
        await set_capability(
            db, school_id=school.id, role="principal",
            domain="nonexistent", action="read", enabled=True,
        )


@pytest.mark.asyncio
async def test_set_capability_invalid_action(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError

    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的操作"):
        await set_capability(
            db, school_id=school.id, role="principal",
            domain="exam", action="execute", enabled=True,
        )
