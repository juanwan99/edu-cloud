"""S1-C Task 1: Class.grade_id 新增字段 + 守旧字段不动验证。

ORC-S1C-002: 禁改 Class.grade / Class.grade_number 两行。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.3
"""
from sqlalchemy import String


def test_class_has_grade_id_fk_to_grades():
    """新增 Class.grade_id: VARCHAR(36) NULLABLE FK→grades.id"""
    from edu_cloud.modules.student.models import Class

    col = Class.__table__.columns.get("grade_id")
    assert col is not None, "Class 必须有 grade_id 列"
    assert isinstance(col.type, String)
    assert col.type.length == 36, f"grade_id 必须 VARCHAR(36)，实际 {col.type.length}"
    assert col.nullable is True

    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks, f"FK target 必须是 grades.id，实际 {fks}"


def test_class_legacy_grade_fields_unchanged():
    """ORC-S1C-002: 守旧字段 grade/grade_number 一字不动"""
    from edu_cloud.modules.student.models import Class

    grade_col = Class.__table__.columns.get("grade")
    assert grade_col is not None, "守旧字段 Class.grade 必须保留"
    assert isinstance(grade_col.type, String)
    assert grade_col.type.length == 50, f"grade 必须 VARCHAR(50)，实际 {grade_col.type.length}"
    assert grade_col.nullable is False, "grade 必须 NOT NULL（守旧字段）"

    gn_col = Class.__table__.columns.get("grade_number")
    assert gn_col is not None, "守旧字段 Class.grade_number 必须保留"
    assert gn_col.nullable is True


def test_class_grade_id_instantiation_optional():
    """Class 不传 grade_id 也能实例化（NULL 是合法值，渐进式迁移）"""
    from edu_cloud.modules.student.models import Class

    c = Class(name="高一1班", grade="高一", school_id="x")  # 不传 grade_id
    assert getattr(c, "grade_id", None) is None
