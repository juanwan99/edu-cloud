"""Tests for ScopeVersionChecker — DB-persisted scope invalidation."""
import pytest

from edu_cloud.ai.scope_version import ScopeVersionChecker


@pytest.mark.asyncio
async def test_no_record_returns_version_1(db):
    checker = ScopeVersionChecker(db)
    v = await checker.get_current_version(school_id="s1", user_id="u1")
    assert v == 1


@pytest.mark.asyncio
async def test_version_match_passes(db):
    checker = ScopeVersionChecker(db)
    is_valid = await checker.is_valid(school_id="s1", user_id="u1", version=1)
    assert is_valid is True


@pytest.mark.asyncio
async def test_version_mismatch_fails(db):
    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="assignment.changed")
    is_valid = await checker.is_valid(school_id="s1", user_id="u1", version=1)
    assert is_valid is False


@pytest.mark.asyncio
async def test_bump_increments_version(db):
    checker = ScopeVersionChecker(db)
    v = await checker.get_current_version(school_id="s1", user_id="u1")
    await checker.bump(school_id="s1", user_id="u1", reason="role.changed")
    v2 = await checker.get_current_version(school_id="s1", user_id="u1")
    assert v2 == v + 1


@pytest.mark.asyncio
async def test_bump_creates_record_with_version_2(db):
    checker = ScopeVersionChecker(db)
    new_v = await checker.bump(school_id="s1", user_id="u1", reason="first.bump")
    assert new_v == 2


@pytest.mark.asyncio
async def test_bump_persists_across_instances(db):
    checker1 = ScopeVersionChecker(db)
    await checker1.bump(school_id="s1", user_id="u1", reason="test")
    checker2 = ScopeVersionChecker(db)
    v = await checker2.get_current_version(school_id="s1", user_id="u1")
    assert v == 2


@pytest.mark.asyncio
async def test_bump_school_affects_all_users(db):
    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="init")
    await checker.bump(school_id="s1", user_id="u2", reason="init")
    await checker.bump_school(school_id="s1", reason="semester.switch")
    v1 = await checker.get_current_version("s1", "u1")
    v2 = await checker.get_current_version("s1", "u2")
    assert v1 == 3  # bump once (→2) + bump_school (→3)
    assert v2 == 3


@pytest.mark.asyncio
async def test_bump_school_no_cross_school_leak(db):
    """bump_school for s1 must not affect s2 users."""
    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="init")
    await checker.bump(school_id="s2", user_id="u2", reason="init")
    await checker.bump_school(school_id="s1", reason="semester.switch")
    v_s2 = await checker.get_current_version("s2", "u2")
    assert v_s2 == 2  # only the individual bump, not affected by s1 bump_school


@pytest.mark.asyncio
async def test_current_version_ge_is_valid(db):
    """version >= current should be valid (e.g. version=3, current=2)."""
    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="test")
    # current is 2, version=3 should still be valid
    assert await checker.is_valid("s1", "u1", version=3) is True


@pytest.mark.asyncio
async def test_bump_stores_reason(db):
    """bump should persist the reason in last_reason."""
    from sqlalchemy import select
    from edu_cloud.models.scope_version import ScopeVersion

    checker = ScopeVersionChecker(db)
    await checker.bump(school_id="s1", user_id="u1", reason="role.changed")
    row = (await db.execute(
        select(ScopeVersion).where(
            ScopeVersion.school_id == "s1",
            ScopeVersion.user_id == "u1",
        )
    )).scalar_one()
    assert row.last_reason == "role.changed"
