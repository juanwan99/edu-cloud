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
