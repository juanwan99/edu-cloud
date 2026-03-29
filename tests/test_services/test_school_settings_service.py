import pytest
from edu_cloud.models.school_settings import SchoolSetting, SchoolModule


@pytest.mark.asyncio
async def test_school_setting_model(db, seed_school):
    school, _ = seed_school
    setting = SchoolSetting(
        school_id=school.id,
        category="feature",
        key="ai_enabled",
        value='true',
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    assert setting.id is not None
    assert setting.school_id == school.id
    assert setting.key == "ai_enabled"
    assert setting.value == "true"
    assert setting.category == "feature"


@pytest.mark.asyncio
async def test_school_module_model(db, seed_school):
    school, _ = seed_school
    module = SchoolModule(
        school_id=school.id,
        module_code="homework",
        enabled=True,
        config='{}',
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    assert module.id is not None
    assert module.module_code == "homework"
    assert module.enabled is True


@pytest.mark.asyncio
async def test_school_module_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError
    school, _ = seed_school
    m1 = SchoolModule(school_id=school.id, module_code="homework", enabled=True)
    m2 = SchoolModule(school_id=school.id, module_code="homework", enabled=False)
    db.add(m1)
    await db.flush()
    db.add(m2)
    with pytest.raises(IntegrityError):
        await db.flush()
