"""S1-C Task 1: Grade 独立表 ORM + Class.grade_id FK 断言。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.3
refs: docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md Task 3
refs: haofenshu-clone/server/routes/baseinfo.js（对照源）
"""
from sqlalchemy import UniqueConstraint


def test_grade_model_can_import():
    """ORM 入口可 import（走 edu_cloud.models.grade canonical location）"""
    from edu_cloud.models.grade import Grade  # noqa: F401


def test_grade_required_fields():
    """Grade 包含 8 列核心字段（id+school_id+name+grade_level+xueduan+sort_order+created_at+updated_at）"""
    from edu_cloud.models.grade import Grade

    columns = {c.name for c in Grade.__table__.columns}
    required = {"id", "school_id", "name", "grade_level", "xueduan", "sort_order", "created_at", "updated_at"}
    assert required.issubset(columns), f"Missing: {required - columns}"


def test_grade_school_fk_target():
    """Grade.school_id FK 指向 schools.id（IdMixin String(36) 一致）"""
    from edu_cloud.models.grade import Grade

    col = Grade.__table__.columns.get("school_id")
    assert col is not None
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "schools.id" in fks
    assert col.type.length == 36


def test_grade_sort_order_has_default_zero():
    """R2-F002 INV-S1C-001 拆分：sort_order 列必须 default=0（migration server_default='0' 对齐）."""
    from edu_cloud.models.grade import Grade

    col = Grade.__table__.columns.get("sort_order")
    assert col is not None, "Grade 必须有 sort_order 列"
    # ORM 层 default 配置（mapped_column(default=0)）
    assert col.default is not None, "sort_order 必须有 default 值"
    default_arg = getattr(col.default, "arg", None)
    assert default_arg == 0, f"sort_order default 必须为 0，实际 {default_arg!r}"


def test_grade_id_is_string36_not_integer():
    """ORC-S1C-004: grades.id 是 VARCHAR(36) UUID（IdMixin 约定），不是 Integer"""
    from edu_cloud.models.grade import Grade
    from sqlalchemy import String

    id_col = Grade.__table__.columns.get("id")
    assert id_col is not None
    assert isinstance(id_col.type, String)
    assert id_col.type.length == 36
    assert id_col.primary_key is True


def test_grade_unique_school_name():
    """Grade 含 UniqueConstraint(school_id, name) 组合级约束"""
    from edu_cloud.models.grade import Grade

    uq_cols = {
        tuple(sorted(c.name for c in uq.columns))
        for uq in Grade.__table__.constraints
        if isinstance(uq, UniqueConstraint)
    }
    # 断言存在一个 UniqueConstraint 恰好覆盖 {school_id, name}
    assert ("name", "school_id") in uq_cols or ("school_id", "name") in uq_cols, \
        f"Missing UniqueConstraint(school_id, name) in {uq_cols}"
