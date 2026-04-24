from datetime import date, time

from sqlalchemy import String, Integer, Boolean, Date, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Semester(Base, IdMixin, TimestampMixin):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("school_id", "school_year", "term", name="uq_semester"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    school_year: Mapped[str] = mapped_column(String(20))
    term: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class TimePeriod(Base, IdMixin):
    __tablename__ = "time_periods"
    __table_args__ = (
        UniqueConstraint("school_id", "semester_id", "period_number", name="uq_time_period"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    period_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    period_type: Mapped[str] = mapped_column(String(20))


class TimetableSlot(Base, IdMixin):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint("class_id", "semester_id", "weekday", "period_id", name="uq_timetable_slot"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    period_id: Mapped[str] = mapped_column(String(36), ForeignKey("time_periods.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    room: Mapped[str | None] = mapped_column(String(50), default=None)
