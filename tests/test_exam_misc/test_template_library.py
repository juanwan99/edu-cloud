"""内置模板库测试。"""
import pytest
from edu_cloud.modules.card.template_library import (
    get_builtin_template,
    list_builtin_subjects,
    extract_fixed_parts,
)


def test_list_builtin_subjects():
    subjects = list_builtin_subjects()
    assert "生物" in subjects
    assert "语文" in subjects
    assert "数学" in subjects
    assert len(subjects) == 9


def test_get_builtin_template_exists():
    tpl = get_builtin_template("生物")
    assert tpl is not None
    assert tpl["subject"] == "生物"
    assert "anchors" in tpl
    assert "regions" in tpl
    assert "image_size" in tpl


def test_get_builtin_template_not_found():
    tpl = get_builtin_template("日语")
    assert tpl is None


def test_extract_fixed_parts():
    tpl = get_builtin_template("生物")
    fixed = extract_fixed_parts(tpl)
    assert "anchors" in fixed
    assert "objective_regions" in fixed
    assert "image_size" in fixed
    assert "columns" in fixed
    # 生物有 16 个 OBJ regions
    assert len(fixed["objective_regions"]) == 16
    # anchors = 4
    assert len(fixed["anchors"]) == 4
    # columns 应有栏信息
    assert len(fixed["columns"]) >= 1


def test_extract_fixed_parts_derives_columns():
    """columns 从主观题 regions 的 x 坐标聚类推导。"""
    tpl = get_builtin_template("生物")
    fixed = extract_fixed_parts(tpl)
    # 生物模板有 3 栏（Q01 在左栏，Q02-Q03 在中栏，Q04-Q05 在右栏）
    for col in fixed["columns"]:
        assert "id" in col
        assert "x1" in col
        assert "x2" in col
        assert "y1" in col
        assert "y2" in col
