"""Grade 独立表（S1-C 1.3，refs: design §4 1.3 / 附录 D §Gap#1 / haofenshu-clone/server/routes/baseinfo.js）。

跨模块共享表下沉 models/ 顶层（orm-placement.md §7）；被 S2 组卷 / S3 学情画像 / S4 教学计划消费。

Class.grade_id 为本 plan 新加 FK 指向本表，
同时保留 Class.grade 字符串列以支持渐进式迁移（ORC-S1C-002）。
"""
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Grade(Base, IdMixin, TimestampMixin):
    """年级实体（校内按 name 唯一，跨校允许重名）。"""
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_grade_school_name"),)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(50))
    grade_level: Mapped[int | None] = mapped_column(Integer, default=None)
    xueduan: Mapped[str | None] = mapped_column(String(20), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
