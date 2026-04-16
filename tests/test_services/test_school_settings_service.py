import pytest
from edu_cloud.models.school_settings import SchoolSetting, SchoolModule, DEFAULT_ENABLED
from edu_cloud.services.school_settings_service import (
    get_settings, upsert_setting, get_enabled_modules,
    set_module_enabled, init_school_modules,
)


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
async def test_school_setting_unique_constraint(db, seed_school):
    """Same school + same key → IntegrityError (F-05 fix)."""
    from sqlalchemy.exc import IntegrityError
    school, _ = seed_school
    s1 = SchoolSetting(school_id=school.id, category="feature", key="ai_enabled", value="true")
    s2 = SchoolSetting(school_id=school.id, category="feature", key="ai_enabled", value="false")
    db.add(s1)
    await db.flush()
    db.add(s2)
    with pytest.raises(IntegrityError):
        await db.flush()


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


# ── Service tests ──


@pytest.mark.asyncio
async def test_upsert_setting_create(db, seed_school):
    school, _ = seed_school
    result = await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="true")
    assert result.key == "ai"
    assert result.value == "true"


@pytest.mark.asyncio
async def test_upsert_setting_update(db, seed_school):
    school, _ = seed_school
    await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="true")
    result = await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="false")
    assert result.value == "false"


@pytest.mark.asyncio
async def test_get_settings(db, seed_school):
    school, _ = seed_school
    await upsert_setting(db, school_id=school.id, category="feature", key="a", value="1")
    await upsert_setting(db, school_id=school.id, category="exam", key="b", value="2")
    all_settings = await get_settings(db, school_id=school.id)
    assert len(all_settings) == 2
    feature_only = await get_settings(db, school_id=school.id, category="feature")
    assert len(feature_only) == 1


@pytest.mark.asyncio
async def test_init_school_modules(db, seed_school):
    school, _ = seed_school
    await init_school_modules(db, school_id=school.id)
    enabled = await get_enabled_modules(db, school_id=school.id)
    assert enabled == DEFAULT_ENABLED


def test_default_enabled_includes_conduct():
    """2026-04-13 conduct R3 上线契约——防止有人意外回退默认启用集。
    若 conduct 不在默认集 → 新建学校 sidebar 全部 9 个德育菜单被隐藏。"""
    assert "conduct" in DEFAULT_ENABLED, (
        "DEFAULT_ENABLED 必须包含 'conduct'：移除会导致新建学校隐藏全部德育菜单。"
        f" 当前: {DEFAULT_ENABLED}"
    )


@pytest.mark.asyncio
async def test_set_module_enabled(db, seed_school):
    school, _ = seed_school
    await init_school_modules(db, school_id=school.id)
    await set_module_enabled(db, school_id=school.id, module_code="homework", enabled=True)
    enabled = await get_enabled_modules(db, school_id=school.id)
    assert "homework" in enabled


@pytest.mark.asyncio
async def test_set_module_invalid_code(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的模块代码"):
        await set_module_enabled(db, school_id=school.id, module_code="nonexistent", enabled=True)
