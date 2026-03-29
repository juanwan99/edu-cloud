import pytest
from edu_cloud.models.subject_selection import SubjectSelection
from edu_cloud.services.subject_selection_service import (
    list_selections, create_selection, update_selection, delete_selection,
)


@pytest.mark.asyncio
async def test_subject_selection_model(db, seed_school):
    school, _ = seed_school
    sel = SubjectSelection(
        school_id=school.id, name="物化生",
        subject_codes=["physics", "chemistry", "biology"],
        mode="3+1+2",
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    assert sel.id is not None
    assert sel.name == "物化生"
    assert sel.subject_codes == ["physics", "chemistry", "biology"]
    assert sel.is_active is True


@pytest.mark.asyncio
async def test_subject_selection_unique_name(db, seed_school):
    from sqlalchemy.exc import IntegrityError
    school, _ = seed_school
    s1 = SubjectSelection(school_id=school.id, name="物化生", subject_codes=["physics"])
    s2 = SubjectSelection(school_id=school.id, name="物化生", subject_codes=["chemistry"])
    db.add(s1)
    await db.flush()
    db.add(s2)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_create_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(
        db, school_id=school.id, name="史地政",
        subject_codes=["history", "geography", "politics"], mode="3+1+2",
    )
    assert sel.name == "史地政"
    assert sel.mode == "3+1+2"


@pytest.mark.asyncio
async def test_create_selection_invalid_mode(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的选考模式"):
        await create_selection(
            db, school_id=school.id, name="无效模式",
            subject_codes=["physics"], mode="invalid",
        )


@pytest.mark.asyncio
async def test_create_selection_too_many_subjects(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="科目数量"):
        await create_selection(
            db, school_id=school.id, name="过多科目",
            subject_codes=["a", "b", "c", "d", "e", "f", "g", "h"],
        )


@pytest.mark.asyncio
async def test_create_selection_empty_subjects(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="科目数量"):
        await create_selection(
            db, school_id=school.id, name="空科目", subject_codes=[],
        )


@pytest.mark.asyncio
async def test_create_selection_duplicate_name(db, seed_school):
    """P1 fix: duplicate name in same school → ConflictError, not 500."""
    from edu_cloud.services.exceptions import ConflictError
    school, _ = seed_school
    await create_selection(db, school_id=school.id, name="重复组合", subject_codes=["physics"])
    with pytest.raises(ConflictError, match="同名"):
        await create_selection(db, school_id=school.id, name="重复组合", subject_codes=["chemistry"])


@pytest.mark.asyncio
async def test_list_selections_filter(db, seed_school):
    school, _ = seed_school
    await create_selection(db, school_id=school.id, name="组合A", subject_codes=["physics"])
    sel_b = await create_selection(db, school_id=school.id, name="组合B", subject_codes=["history"], mode="3+3")
    await update_selection(db, school_id=school.id, selection_id=sel_b.id, is_active=False)
    active = await list_selections(db, school_id=school.id, is_active=True)
    assert len(active) == 1
    assert active[0].name == "组合A"


@pytest.mark.asyncio
async def test_update_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(db, school_id=school.id, name="更新测试", subject_codes=["physics"])
    updated = await update_selection(
        db, school_id=school.id, selection_id=sel.id,
        name="更新后", subject_codes=["chemistry", "biology"],
    )
    assert updated.name == "更新后"
    assert updated.subject_codes == ["chemistry", "biology"]


@pytest.mark.asyncio
async def test_delete_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(db, school_id=school.id, name="删除测试", subject_codes=["physics"])
    await delete_selection(db, school_id=school.id, selection_id=sel.id)
    rows = await list_selections(db, school_id=school.id)
    assert len(rows) == 0
