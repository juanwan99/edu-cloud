"""S1-C Task 3: PaperAccessLevel 枚举常量 + bank_questions.grade_id 类型修正断言。

F006 反逻辑镜像修正：不用 `{e.value for e in Enum} == {"a","b","c"}` 这种集合相等断言，
改用外部字符串 round-trip 锚定每个值，防止重命名漂移。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.5
"""
from enum import Enum

import pytest


def test_paper_access_level_import():
    from edu_cloud.modules.paper.constants import PaperAccessLevel  # noqa: F401


def test_paper_access_level_is_str_enum():
    """PaperAccessLevel 是 str + Enum 双继承（支持字符串比较）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    assert issubclass(PaperAccessLevel, str)
    assert issubclass(PaperAccessLevel, Enum)


@pytest.mark.parametrize("external_value,expected_member_name", [
    ("teacher_private", "TEACHER_PRIVATE"),
    ("school_shared", "SCHOOL_SHARED"),
    ("district_shared", "DISTRICT_SHARED"),
])
def test_paper_access_level_roundtrip_via_value(external_value: str, expected_member_name: str):
    """F006 反镜像：外部字符串 → 枚举成员 → 回到字符串，每个成员独立断言。

    错误实现（值漂移到 `teacher_pr`）会让 `PaperAccessLevel("teacher_private")` 抛 ValueError，立即 fail。
    集合相等断言（parent L1 plan Task 5 Step 5.1 的 `assert values == {"teacher_private",...}`）
    在值漂移 + 名字漂移同步发生时会假绿——本 test 钉死字符串值。
    """
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    member = PaperAccessLevel(external_value)  # 值→成员
    assert member.name == expected_member_name
    assert member.value == external_value      # 成员→值
    assert member == external_value            # str-Enum 字符串比较


def test_paper_access_level_rejects_unknown_value():
    """F006 反镜像：未知值必须抛 ValueError（而非静默退化）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    with pytest.raises(ValueError):
        PaperAccessLevel("platform_shared")  # 不在 3 成员值中


def test_paper_access_level_has_exactly_three_members():
    """成员数量钉死为 3（多加/少加都 fail）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    assert len(list(PaperAccessLevel)) == 3


def test_bank_grade_id_is_string36_fk():
    """ORC-S1C-004: bank_questions.grade_id ORM 层改 String(36) + FK → grades.id"""
    from edu_cloud.modules.bank.models import BankQuestion
    from sqlalchemy import String

    col = BankQuestion.__table__.columns.get("grade_id")
    assert col is not None
    assert isinstance(col.type, String), f"grade_id 必须 String 类型，实际 {type(col.type).__name__}"
    assert col.type.length == 36, f"grade_id 必须 VARCHAR(36)，实际 {col.type.length}"
    assert col.nullable is True

    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks, f"FK target 必须是 grades.id，实际 {fks}"


def test_bank_s1a_fields_preserved():
    """ORC-S1C-002 扩展：S1-A 新加 5 字段中除 grade_id 外，其他 4 个字段不动"""
    from edu_cloud.modules.bank.models import BankQuestion
    from sqlalchemy import String, Text, JSON

    def _col(name):
        return BankQuestion.__table__.columns.get(name)

    source_col = _col("source")
    assert source_col is not None
    assert isinstance(source_col.type, String)
    assert source_col.type.length == 20

    explanation_col = _col("explanation")
    assert explanation_col is not None
    assert isinstance(explanation_col.type, Text)

    kp_col = _col("knowledge_point_ids")
    assert kp_col is not None
    assert isinstance(kp_col.type, JSON)

    dl_col = _col("difficulty_level")
    assert dl_col is not None
    assert isinstance(dl_col.type, String)
    assert dl_col.type.length == 10
