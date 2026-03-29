from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school_settings import (
    SchoolSetting, SchoolModule, MODULE_CODES, DEFAULT_ENABLED,
)
from edu_cloud.services.exceptions import ValidationError


async def get_settings(
    db: AsyncSession, *, school_id: str, category: str | None = None,
) -> list[SchoolSetting]:
    stmt = select(SchoolSetting).where(SchoolSetting.school_id == school_id)
    if category:
        stmt = stmt.where(SchoolSetting.category == category)
    result = await db.execute(stmt.order_by(SchoolSetting.category, SchoolSetting.key))
    return list(result.scalars().all())


async def upsert_setting(
    db: AsyncSession, *, school_id: str, category: str, key: str, value: str | None,
) -> SchoolSetting:
    stmt = select(SchoolSetting).where(
        SchoolSetting.school_id == school_id, SchoolSetting.key == key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.value = value
        existing.category = category
    else:
        existing = SchoolSetting(school_id=school_id, category=category, key=key, value=value)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def get_enabled_modules(db: AsyncSession, *, school_id: str) -> set[str]:
    stmt = select(SchoolModule.module_code).where(
        SchoolModule.school_id == school_id, SchoolModule.enabled.is_(True),
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def init_school_modules(db: AsyncSession, *, school_id: str) -> None:
    for code in MODULE_CODES:
        existing = (await db.execute(
            select(SchoolModule).where(
                SchoolModule.school_id == school_id, SchoolModule.module_code == code,
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(SchoolModule(
                school_id=school_id,
                module_code=code,
                enabled=(code in DEFAULT_ENABLED),
            ))
    await db.commit()


async def set_module_enabled(
    db: AsyncSession, *, school_id: str, module_code: str, enabled: bool,
) -> SchoolModule:
    if module_code not in MODULE_CODES:
        raise ValidationError(f"无效的模块代码: {module_code}")
    stmt = select(SchoolModule).where(
        SchoolModule.school_id == school_id, SchoolModule.module_code == module_code,
    )
    module = (await db.execute(stmt)).scalar_one_or_none()
    if not module:
        module = SchoolModule(school_id=school_id, module_code=module_code, enabled=enabled)
        db.add(module)
    else:
        module.enabled = enabled
    await db.commit()
    await db.refresh(module)
    return module


async def get_all_modules(db: AsyncSession, *, school_id: str) -> list[dict]:
    stmt = select(SchoolModule).where(SchoolModule.school_id == school_id)
    result = await db.execute(stmt)
    existing = {m.module_code: m for m in result.scalars().all()}
    return [
        {
            "code": code,
            "name": name,
            "enabled": existing[code].enabled if code in existing else (code in DEFAULT_ENABLED),
            "config": existing[code].config if code in existing else None,
        }
        for code, name in MODULE_CODES.items()
    ]
