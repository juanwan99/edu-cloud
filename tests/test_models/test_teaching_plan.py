"""S1-C Task 2: TeachingPlan 骨架 ORM 断言。

ORC-S1C-003: 骨架 FK 目标 ⊂ {schools.id, grades.id, users.id}，不含 lesson_plans 等未建表。
R2-F001 修正: canonical location 挪到 src/edu_cloud/models/teaching_plan.py
    （与 Grade 一致 platform-level 跨模块共享表）。三入口 env.py + app.py + conftest.py
    各加独立 import（禁止继续依赖 conftest-only / calendar-models 注册）。
R2-F002 修正: INV-S1C-002 拆分为 schools/grades/users 三个 FK 独立断言
    （避免"子集断言"在漏 created_by→users FK 时假绿）。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.4
refs: haofenshu-clone/server/config/schema.sql:284-302
"""
from sqlalchemy import UniqueConstraint


def test_teaching_plan_import_from_models():
    """R2-F001 修正: canonical location 在 src/edu_cloud/models/teaching_plan.py."""
    from edu_cloud.models.teaching_plan import TeachingPlan  # noqa: F401


def test_teaching_plan_required_fields():
    """骨架含 9 列（id + 7 业务 + 2 timestamps）."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    cols = {c.name for c in TeachingPlan.__table__.columns}
    required = {
        "id", "school_id", "subject_code", "grade_id", "semester",
        "weeks_json", "created_by", "created_at", "updated_at",
    }
    assert required.issubset(cols), f"Missing: {required - cols}"


def _fk_targets_for_column(table, column_name: str) -> set[str]:
    col = table.columns.get(column_name)
    assert col is not None, f"TeachingPlan 缺列 {column_name}"
    return {fk.target_fullname for fk in col.foreign_keys}


def test_teaching_plan_school_id_fk_targets_schools():
    """R2-F002 INV-S1C-002a: school_id → schools.id FK 独立断言."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    assert "schools.id" in _fk_targets_for_column(
        TeachingPlan.__table__, "school_id"
    ), "INV-S1C-002a 违反：school_id 必须 FK→schools.id"


def test_teaching_plan_grade_id_fk_targets_grades():
    """R2-F002 INV-S1C-002b: grade_id → grades.id FK 独立断言."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    assert "grades.id" in _fk_targets_for_column(
        TeachingPlan.__table__, "grade_id"
    ), "INV-S1C-002b 违反：grade_id 必须 FK→grades.id"


def test_teaching_plan_created_by_fk_targets_users():
    """R2-F002 INV-S1C-002c: created_by → users.id FK 独立断言（R2 核心：原 '子集断言' 会漏此条）."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    assert "users.id" in _fk_targets_for_column(
        TeachingPlan.__table__, "created_by"
    ), "INV-S1C-002c 违反：created_by 必须 FK→users.id"


def test_teaching_plans_fk_targets_no_excess():
    """ORC-S1C-003 综合断言：全部 FK ⊂ {schools/grades/users}，严禁 lesson_plans 等未建表 FK."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    all_targets = set()
    for col in TeachingPlan.__table__.columns:
        for fk in col.foreign_keys:
            all_targets.add(fk.target_fullname)

    allowed = {"schools.id", "grades.id", "users.id"}
    excess = all_targets - allowed
    assert not excess, \
        f"TeachingPlan 有未建表 FK：{excess}（ORC-S1C-003 违反）"


def test_teaching_plan_unique_constraint():
    """含 UniqueConstraint(school_id, subject_code, grade_id, semester)."""
    from edu_cloud.models.teaching_plan import TeachingPlan

    uq_cols_sets = [
        frozenset(c.name for c in uq.columns)
        for uq in TeachingPlan.__table__.constraints
        if isinstance(uq, UniqueConstraint)
    ]
    expected = frozenset({"school_id", "subject_code", "grade_id", "semester"})
    assert expected in uq_cols_sets, \
        f"Missing UniqueConstraint(school_id, subject_code, grade_id, semester) in {uq_cols_sets}"


def test_calendar_re_exports_still_work():
    """R2-F001 修正后：calendar/models.py 保持 re-export stub，TeachingPlan 挪出不影响既有 re-export."""
    from edu_cloud.modules.calendar.models import (  # noqa: F401
        CalendarEvent, NotificationRule, Notification,
    )
