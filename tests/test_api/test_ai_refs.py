from edu_cloud.ai.ref_types import REF_TYPES, RefType, RefItem


def test_ref_types_registry():
    assert len(REF_TYPES) >= 5
    codes = [t.type_code for t in REF_TYPES]
    assert "exam" in codes
    assert "class" in codes
    assert "student" in codes


def test_exam_has_children_type():
    exam = next(t for t in REF_TYPES if t.type_code == "exam")
    assert exam.children_type == "subject"


def test_ref_item_to_dict():
    item = RefItem(id="abc", label="Test", subtitle="sub", children_type="subject")
    d = item.to_dict()
    assert d == {"id": "abc", "label": "Test", "subtitle": "sub", "children_type": "subject"}


def test_ref_item_minimal():
    item = RefItem(id="x", label="Y")
    d = item.to_dict()
    assert d["children_type"] is None
    assert d["subtitle"] is None
