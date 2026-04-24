# src/edu_cloud/modules/academic/service.py
import logging
from datetime import date as date_type, time as time_type

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.academic.models import Semester, TimePeriod, TimetableSlot
from edu_cloud.services.exceptions import NotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)

VALID_PERIOD_TYPES = {"class", "break", "activity", "self_study"}


# ── Semester ────────────────────────────────────────────────────

async def create_semester(
    db: AsyncSession, *, school_id: str, name: str,
    school_year: str, term: int,
    start_date: date_type, end_date: date_type,
) -> dict:
    if term not in (1, 2):
        raise ValidationError("term 必须为 1 或 2")
    if start_date >= end_date:
        raise ValidationError("start_date 必须早于 end_date")

    semester = Semester(
        school_id=school_id, name=name, school_year=school_year,
        term=term, start_date=start_date, end_date=end_date,
    )
    db.add(semester)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise ConflictError("该学年+学期已存在")
    await db.refresh(semester)
    return _semester_dict(semester)


async def list_semesters(
    db: AsyncSession, *, school_id: str, school_year: str | None = None,
) -> list[dict]:
    stmt = select(Semester).where(Semester.school_id == school_id)
    if school_year:
        stmt = stmt.where(Semester.school_year == school_year)
    stmt = stmt.order_by(Semester.school_year.desc(), Semester.term.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_semester_dict(s) for s in rows]


async def get_current_semester(db: AsyncSession, *, school_id: str) -> dict | None:
    stmt = (
        select(Semester)
        .where(Semester.school_id == school_id, Semester.is_current == True)  # noqa: E712
    )
    s = (await db.execute(stmt)).scalar_one_or_none()
    return _semester_dict(s) if s else None


async def update_semester(
    db: AsyncSession, *, semester_id: str, school_id: str, **fields,
) -> dict:
    semester = await _get_semester(db, semester_id, school_id)
    for k, v in fields.items():
        if v is not None and hasattr(semester, k):
            setattr(semester, k, v)
    await db.commit()
    await db.refresh(semester)
    return _semester_dict(semester)


async def activate_semester(
    db: AsyncSession, *, semester_id: str, school_id: str,
) -> dict:
    semester = await _get_semester(db, semester_id, school_id)
    await db.execute(
        update(Semester)
        .where(Semester.school_id == school_id)
        .values(is_current=False)
    )
    semester.is_current = True
    await db.commit()
    await db.refresh(semester)
    return _semester_dict(semester)


async def _get_semester(db: AsyncSession, semester_id: str, school_id: str) -> Semester:
    semester = await db.get(Semester, semester_id)
    if not semester or semester.school_id != school_id:
        raise NotFoundError("学期不存在")
    return semester


def _semester_dict(s: Semester) -> dict:
    return {
        "id": s.id, "name": s.name,
        "school_year": s.school_year, "term": s.term,
        "start_date": str(s.start_date), "end_date": str(s.end_date),
        "is_current": s.is_current,
    }


# ── TimePeriod ──────────────────────────────────────────────────

async def set_periods(
    db: AsyncSession, *, school_id: str, semester_id: str,
    periods: list[dict],
) -> list[dict]:
    await _get_semester(db, semester_id, school_id)

    for p in periods:
        if p.get("period_type") not in VALID_PERIOD_TYPES:
            raise ValidationError(f"无效的 period_type: {p.get('period_type')}")

    await db.execute(
        delete(TimePeriod).where(
            TimePeriod.school_id == school_id,
            TimePeriod.semester_id == semester_id,
        )
    )

    new_periods = []
    for p in periods:
        tp = TimePeriod(
            school_id=school_id, semester_id=semester_id,
            period_number=p["period_number"], name=p["name"],
            start_time=time_type.fromisoformat(p["start_time"]),
            end_time=time_type.fromisoformat(p["end_time"]),
            period_type=p["period_type"],
        )
        db.add(tp)
        new_periods.append(tp)

    await db.commit()
    for tp in new_periods:
        await db.refresh(tp)
    return [_period_dict(tp) for tp in new_periods]


async def get_periods(
    db: AsyncSession, *, school_id: str, semester_id: str,
) -> list[dict]:
    stmt = (
        select(TimePeriod)
        .where(TimePeriod.school_id == school_id, TimePeriod.semester_id == semester_id)
        .order_by(TimePeriod.period_number)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_period_dict(tp) for tp in rows]


def _period_dict(tp: TimePeriod) -> dict:
    return {
        "id": tp.id, "period_number": tp.period_number,
        "name": tp.name,
        "start_time": tp.start_time.isoformat(),
        "end_time": tp.end_time.isoformat(),
        "period_type": tp.period_type,
    }


# ── Timetable ───────────────────────────────────────────────────

async def save_timetable(
    db: AsyncSession, *, school_id: str, semester_id: str, class_id: str,
    slots: list[dict],
) -> dict:
    await _get_semester(db, semester_id, school_id)

    conflicts = await _check_teacher_conflicts(db, school_id, semester_id, class_id, slots)
    if conflicts:
        raise ValidationError(f"教师时间冲突: {conflicts}")

    await db.execute(
        delete(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.semester_id == semester_id,
        )
    )

    new_slots = []
    for s in slots:
        slot = TimetableSlot(
            school_id=school_id, semester_id=semester_id, class_id=class_id,
            weekday=s["weekday"], period_id=s["period_id"],
            subject_code=s["subject_code"], teacher_id=s["teacher_id"],
            room=s.get("room"),
        )
        db.add(slot)
        new_slots.append(slot)

    await db.commit()
    return {"saved": len(new_slots)}


async def get_timetable(
    db: AsyncSession, *, school_id: str, semester_id: str,
    class_id: str | None = None, teacher_id: str | None = None,
) -> list[dict]:
    stmt = select(TimetableSlot).where(
        TimetableSlot.school_id == school_id,
        TimetableSlot.semester_id == semester_id,
    )
    if class_id:
        stmt = stmt.where(TimetableSlot.class_id == class_id)
    if teacher_id:
        stmt = stmt.where(TimetableSlot.teacher_id == teacher_id)
    stmt = stmt.order_by(TimetableSlot.weekday, TimetableSlot.period_id)

    rows = (await db.execute(stmt)).scalars().all()
    return [_slot_dict(s) for s in rows]


async def get_timetable_stats(
    db: AsyncSession, *, school_id: str, semester_id: str, class_id: str,
) -> list[dict]:
    from sqlalchemy import func
    stmt = (
        select(TimetableSlot.subject_code, func.count().label("count"))
        .where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.semester_id == semester_id,
            TimetableSlot.class_id == class_id,
        )
        .group_by(TimetableSlot.subject_code)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"subject_code": r[0], "count": r[1]} for r in rows]


async def _check_teacher_conflicts(
    db: AsyncSession, school_id: str, semester_id: str,
    class_id: str, new_slots: list[dict],
) -> list[str]:
    conflicts = []
    for s in new_slots:
        stmt = (
            select(TimetableSlot)
            .where(
                TimetableSlot.school_id == school_id,
                TimetableSlot.semester_id == semester_id,
                TimetableSlot.teacher_id == s["teacher_id"],
                TimetableSlot.weekday == s["weekday"],
                TimetableSlot.period_id == s["period_id"],
                TimetableSlot.class_id != class_id,
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            conflicts.append(
                f"教师{s['teacher_id']} 在周{s['weekday']}第{s['period_id']}节已有课（班级{existing.class_id}）"
            )
    return conflicts


def _slot_dict(s: TimetableSlot) -> dict:
    return {
        "id": s.id, "class_id": s.class_id,
        "weekday": s.weekday, "period_id": s.period_id,
        "subject_code": s.subject_code, "teacher_id": s.teacher_id,
        "room": s.room,
    }
