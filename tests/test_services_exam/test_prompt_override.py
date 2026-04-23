import pytest
from edu_cloud.modules.grading.prompt_override import (
    get_prompt_with_override,
    set_prompt_override,
    delete_prompt_override,
    list_prompt_overrides,
)
from edu_cloud.models.school import School


@pytest.fixture
async def school(db):
    s = School(name="Override Test School", code="OTS01")
    db.add(s)
    await db.commit()
    return s


@pytest.mark.asyncio
async def test_get_prompt_no_override(db, school):
    """Without override, returns code default."""
    prompt = await get_prompt_with_override(
        db, "biology", "GRADING", "senior", school_id=school.id,
    )
    assert prompt is not None
    assert "{{fullScore}}" in prompt


@pytest.mark.asyncio
async def test_get_prompt_with_override(db, school):
    """With override, returns school-specific prompt."""
    custom = "Custom school prompt for {{fullScore}}"
    await set_prompt_override(db, school.id, "biology", "GRADING", custom)
    await db.commit()

    prompt = await get_prompt_with_override(
        db, "biology", "GRADING", "senior", school_id=school.id,
    )
    assert prompt == custom


@pytest.mark.asyncio
async def test_get_prompt_no_school_id(db):
    """Without school_id, returns code default (no DB lookup)."""
    prompt = await get_prompt_with_override(db, "biology", "GRADING", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


@pytest.mark.asyncio
async def test_set_override_upsert(db, school):
    """Setting override twice updates rather than duplicates."""
    await set_prompt_override(db, school.id, "biology", "GRADING", "v1")
    await db.commit()
    await set_prompt_override(db, school.id, "biology", "GRADING", "v2")
    await db.commit()

    prompt = await get_prompt_with_override(
        db, "biology", "GRADING", "senior", school_id=school.id,
    )
    assert prompt == "v2"


@pytest.mark.asyncio
async def test_delete_override(db, school):
    """After deleting override, falls back to code default."""
    await set_prompt_override(db, school.id, "biology", "GRADING", "custom")
    await db.commit()

    deleted = await delete_prompt_override(db, school.id, "biology", "GRADING")
    await db.commit()
    assert deleted is True

    prompt = await get_prompt_with_override(
        db, "biology", "GRADING", "senior", school_id=school.id,
    )
    assert "{{fullScore}}" in prompt  # back to code default


@pytest.mark.asyncio
async def test_delete_nonexistent(db, school):
    """Deleting non-existent override returns False."""
    deleted = await delete_prompt_override(db, school.id, "biology", "GRADING")
    assert deleted is False


@pytest.mark.asyncio
async def test_list_overrides(db, school):
    """List shows all overrides for a school."""
    await set_prompt_override(db, school.id, "biology", "GRADING", "bio prompt")
    await set_prompt_override(db, school.id, "math", "GRADING", "math prompt")
    await db.commit()

    overrides = await list_prompt_overrides(db, school.id)
    assert len(overrides) == 2
    subjects = {o["subject"] for o in overrides}
    assert subjects == {"biology", "math"}
