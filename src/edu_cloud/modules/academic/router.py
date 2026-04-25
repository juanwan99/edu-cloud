from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.academic import service

router = APIRouter(prefix="/api/v1/academic", tags=["academic"])


def _school_id(current: dict) -> str:
    return current["current_role"].school_id


# ── Schemas ─────────────────────────────────────────────────────

class SemesterCreate(BaseModel):
    name: str
    school_year: str
    term: int
    start_date: date_type
    end_date: date_type


class SemesterUpdate(BaseModel):
    name: str | None = None
    start_date: date_type | None = None
    end_date: date_type | None = None


class PeriodItem(BaseModel):
    period_number: int
    name: str
    start_time: str
    end_time: str
    period_type: str


class PeriodBatch(BaseModel):
    semester_id: str
    periods: list[PeriodItem]


# ── Semester endpoints ──────────────────────────────────────────

@router.post("/semesters", status_code=201)
async def create_semester(
    body: SemesterCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.create_semester(
        db, school_id=_school_id(current),
        name=body.name, school_year=body.school_year, term=body.term,
        start_date=body.start_date, end_date=body.end_date,
    )


@router.get("/semesters")
async def list_semesters(
    school_year: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.list_semesters(
        db, school_id=_school_id(current), school_year=school_year,
    )


@router.get("/semesters/current")
async def get_current_semester(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await service.get_current_semester(db, school_id=_school_id(current))
    if not result:
        return {"detail": "未设置当前学期"}
    return result


@router.patch("/semesters/{semester_id}")
async def update_semester(
    semester_id: str,
    body: SemesterUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.update_semester(
        db, semester_id=semester_id, school_id=_school_id(current),
        **body.model_dump(exclude_none=True),
    )


@router.post("/semesters/{semester_id}/activate")
async def activate_semester(
    semester_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.activate_semester(
        db, semester_id=semester_id, school_id=_school_id(current),
    )


# ── Period endpoints ────────────────────────────────────────────

@router.put("/periods")
async def set_periods(
    body: PeriodBatch,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.set_periods(
        db, school_id=_school_id(current), semester_id=body.semester_id,
        periods=[p.model_dump() for p in body.periods],
    )


@router.get("/periods")
async def get_periods(
    semester_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.get_periods(
        db, school_id=_school_id(current), semester_id=semester_id,
    )


# ── Timetable schemas ───────────────────────────────────────────

class TimetableSlotItem(BaseModel):
    weekday: int
    period_id: str
    subject_code: str
    teacher_id: str
    room: str | None = None


class TimetableSave(BaseModel):
    semester_id: str
    slots: list[TimetableSlotItem]


# ── Timetable endpoints ────────────────────────────────────────

@router.get("/timetable")
async def get_timetable(
    semester_id: str = Query(...),
    class_id: str | None = Query(None),
    teacher_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    if not class_id and not teacher_id:
        return {"detail": "必须提供 class_id 或 teacher_id"}
    return await service.get_timetable(
        db, school_id=_school_id(current), semester_id=semester_id,
        class_id=class_id, teacher_id=teacher_id,
    )


@router.put("/timetable/{class_id}")
async def save_timetable(
    class_id: str,
    body: TimetableSave,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.save_timetable(
        db, school_id=_school_id(current), semester_id=body.semester_id,
        class_id=class_id, slots=[s.model_dump() for s in body.slots],
    )


@router.get("/timetable/stats")
async def get_timetable_stats(
    semester_id: str = Query(...),
    class_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.get_timetable_stats(
        db, school_id=_school_id(current), semester_id=semester_id,
        class_id=class_id,
    )
