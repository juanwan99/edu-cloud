"""TeachingPlan 骨架表（S1-C 1.4，R2-F001 修正：canonical 挪到 models/ 顶层）。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.4
refs: 附录 C §Gap#6 / haofenshu-clone/server/config/schema.sql:284-302

跨模块共享表下沉 models/ 顶层（与 Grade 一致 platform-level）。
被 S4 4.3 calendar.teaching_plan_service 消费扩展业务字段。
ORC-S1C-003: 骨架仅含 schools/grades/users 三表 FK；lesson_plans 等 S4 才建的表 FK 严禁加。

注：R2-F001 修正前原设计是追加到 modules/calendar/models.py + 仅 conftest.py 注册，
Planner 调研阶段误读 app.py 的 `import edu_cloud.models.calendar` 语义（以为它加载
modules/calendar/models.py）。真实代码中 app.py/env.py 都只 import models/calendar.py
（CalendarEvent/NotificationRule 定义文件），不触发 modules/calendar/models.py 加载。
canonical 挪到 models/teaching_plan.py 后三入口独立 import 即可 fail-closed。
"""
from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class TeachingPlan(Base, IdMixin, TimestampMixin):
    """教学计划骨架表（学期→周次→知识点，S4 扩展关联资源与审批工作流）。"""
    __tablename__ = "teaching_plans"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "subject_code", "grade_id", "semester",
            name="uq_teaching_plan_scope",
        ),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)
    semester: Mapped[str] = mapped_column(String(30))
    weeks_json: Mapped[list | None] = mapped_column(JSON, default=None)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), default=None)
