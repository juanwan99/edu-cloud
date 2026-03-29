from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.subject_selection import SubjectSelection, VALID_MODES
from edu_cloud.services.exceptions import ValidationError, NotFoundError, ConflictError


def _validate_selection(subject_codes: list, mode: str):
    if not subject_codes or len(subject_codes) > 7:
        raise ValidationError("科目数量必须在 1-7 之间")
    # F02 fix: validate each element is non-empty string
    cleaned = [s.strip() for s in subject_codes if isinstance(s, str)]
    if any(not s for s in cleaned) or len(cleaned) != len(subject_codes):
        raise ValidationError("科目代码不能为空字符串")
    if mode not in VALID_MODES:
        raise ValidationError(f"无效的选考模式: {mode}，可选: {', '.join(VALID_MODES)}")


async def list_selections(
    db: AsyncSession, *, school_id: str,
    is_active: bool | None = None, mode: str | None = None,
) -> list[SubjectSelection]:
    stmt = select(SubjectSelection).where(SubjectSelection.school_id == school_id)
    if is_active is not None:
        stmt = stmt.where(SubjectSelection.is_active == is_active)
    if mode:
        stmt = stmt.where(SubjectSelection.mode == mode)
    result = await db.execute(stmt.order_by(SubjectSelection.name))
    return list(result.scalars().all())


async def _check_name_conflict(db: AsyncSession, school_id: str, name: str, exclude_id: str | None = None):
    """Pre-check for duplicate name in same school."""
    stmt = select(SubjectSelection).where(
        SubjectSelection.school_id == school_id,
        SubjectSelection.name == name,
    )
    if exclude_id:
        stmt = stmt.where(SubjectSelection.id != exclude_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"同名选考组合已存在: {name}")


async def create_selection(
    db: AsyncSession, *, school_id: str, name: str,
    subject_codes: list[str], mode: str = "custom",
) -> SubjectSelection:
    _validate_selection(subject_codes, mode)
    await _check_name_conflict(db, school_id, name)
    sel = SubjectSelection(
        school_id=school_id, name=name,
        subject_codes=subject_codes, mode=mode,
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    return sel


async def update_selection(
    db: AsyncSession, *, school_id: str, selection_id: str, **kwargs,
) -> SubjectSelection:
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id,
            SubjectSelection.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not sel:
        raise NotFoundError("选考组合不存在")
    # F01 fix: pre-check name conflict on rename
    if "name" in kwargs and kwargs["name"] is not None and kwargs["name"] != sel.name:
        await _check_name_conflict(db, school_id, kwargs["name"], exclude_id=selection_id)
    for key, value in kwargs.items():
        if key == "subject_codes" and value is not None:
            _validate_selection(value, kwargs.get("mode", sel.mode))
        if key == "mode" and value is not None:
            _validate_selection(kwargs.get("subject_codes", sel.subject_codes), value)
        if hasattr(sel, key) and value is not None:
            setattr(sel, key, value)
    await db.commit()
    await db.refresh(sel)
    return sel


async def delete_selection(
    db: AsyncSession, *, school_id: str, selection_id: str,
) -> None:
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id,
            SubjectSelection.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not sel:
        raise NotFoundError("选考组合不存在")
    await db.delete(sel)
    await db.commit()
