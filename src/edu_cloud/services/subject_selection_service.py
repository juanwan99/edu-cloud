from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.subject_selection import SubjectSelection, VALID_MODES
from edu_cloud.services.exceptions import ValidationError, NotFoundError, ConflictError


def _validate_selection(subject_codes: list, mode: str):
    if not subject_codes or len(subject_codes) > 7:
        raise ValidationError("科目数量必须在 1-7 之间")
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


async def create_selection(
    db: AsyncSession, *, school_id: str, name: str,
    subject_codes: list[str], mode: str = "custom",
) -> SubjectSelection:
    _validate_selection(subject_codes, mode)
    sel = SubjectSelection(
        school_id=school_id, name=name,
        subject_codes=subject_codes, mode=mode,
    )
    db.add(sel)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"同名选考组合已存在: {name}")
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
