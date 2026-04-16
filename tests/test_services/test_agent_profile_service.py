import pytest
from edu_cloud.models.agent_profile import AgentProfile, AgentRun


@pytest.mark.asyncio
async def test_create_agent_profile(db):
    profile = AgentProfile(
        owner_user_id="user-uuid-1",
        school_id="school-uuid-1",
        profile_type="employee",
        display_name="张老师的助手",
    )
    db.add(profile)
    await db.flush()
    assert profile.id is not None
    assert profile.profile_type == "employee"
    assert profile.preferences is None
    assert profile.memory_summary is None


@pytest.mark.asyncio
async def test_agent_profile_unique_constraint(db):
    """同一用户同一学校只能有一个 profile"""
    from sqlalchemy.exc import IntegrityError
    p1 = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="A",
    )
    p2 = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="B",
    )
    db.add(p1)
    await db.flush()
    db.add(p2)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_create_agent_run(db):
    profile = AgentProfile(
        owner_user_id="user-1", school_id="school-1",
        profile_type="employee", display_name="Test",
    )
    db.add(profile)
    await db.flush()

    run = AgentRun(
        profile_id=profile.id,
        session_id="sess-123",
        tools_resolved=["tool_a", "tool_b", "tool_c"],
        tools_selected=["tool_a"],
        model_used="gpt-5-mini",
        model_tier="mini",
        intent_domains=["exam"],
        token_input=100,
        token_output=50,
    )
    db.add(run)
    await db.flush()
    assert run.id is not None
    assert run.tools_resolved == ["tool_a", "tool_b", "tool_c"]


@pytest.mark.asyncio
async def test_agent_profile_system_type(db):
    profile = AgentProfile(
        owner_user_id="system", school_id="school-1",
        profile_type="system", display_name="巡检 Agent",
    )
    db.add(profile)
    await db.flush()
    assert profile.profile_type == "system"


# ── AgentProfileService tests ──


from edu_cloud.services.agent_profile_service import AgentProfileService


@pytest.mark.asyncio
async def test_get_or_create_creates_new(db):
    profile = await AgentProfileService.get_or_create(
        db, user_id="user-new", school_id="school-1", display_name="新用户"
    )
    assert profile.id is not None
    assert profile.owner_user_id == "user-new"
    assert profile.display_name == "新用户"


@pytest.mark.asyncio
async def test_get_or_create_returns_existing(db):
    p1 = await AgentProfileService.get_or_create(
        db, user_id="user-exist", school_id="school-1", display_name="First"
    )
    p2 = await AgentProfileService.get_or_create(
        db, user_id="user-exist", school_id="school-1", display_name="Second"
    )
    assert p1.id == p2.id
    assert p2.display_name == "First"  # 不覆盖已有


@pytest.mark.asyncio
async def test_create_agent_run_record(db):
    profile = await AgentProfileService.get_or_create(
        db, user_id="user-run", school_id="school-1", display_name="Run"
    )
    run = await AgentProfileService.record_run(
        db,
        profile_id=profile.id,
        session_id="sess-456",
        tools_resolved=["a", "b"],
        tools_selected=["a"],
        model_used="claude-sonnet-4",
        model_tier="standard",
        intent_domains=["exam", "student"],
        token_input=200,
        token_output=100,
    )
    assert run.id is not None
    assert run.model_tier == "standard"
