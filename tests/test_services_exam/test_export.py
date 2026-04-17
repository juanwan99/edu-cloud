"""切割 JSON 导出测试。"""
import pytest
from edu_cloud.modules.card.export.export import skeleton_to_paperseg_json


@pytest.fixture
def sample_skeleton_and_layout():
    from edu_cloud.modules.card.rendering.layout import build_skeleton_from_spec, allocate_by_weights
    qs = [
        {"number": 1, "question_type": "single_choice", "options_count": 4, "score": 2},
        {"number": 2, "question_type": "single_choice", "options_count": 4, "score": 2},
        {"number": 3, "question_type": "multi_choice", "options_count": 4, "score": 3},
        {"number": 4, "question_type": "short_answer", "score": 10,
         "answer_text": "答案" * 10, "image_count": 0, "weight": 0.5},
        {"number": 5, "question_type": "essay", "score": 15,
         "answer_text": "答案" * 30, "image_count": 1, "weight": 0.5},
    ]
    skeleton = build_skeleton_from_spec(qs, paper_size="A3", columns=3, exam_number_digits=8)
    subjectives = [q for q in qs if q["question_type"] in ("short_answer", "essay")]
    weights = [{"number": q["number"], "weight": q["weight"],
                "parsed_structure": [{"sub": 1, "score": q["score"],
                                      "space_type": "essay", "estimated_lines": 0}]}
               for q in subjectives]
    layout = allocate_by_weights(weights, skeleton["columns"])
    return skeleton, layout


class TestPaperSegExport:
    def test_has_required_fields(self, sample_skeleton_and_layout):
        skeleton, layout = sample_skeleton_and_layout
        result = skeleton_to_paperseg_json(skeleton, layout, "E001", "生物")
        assert result["version"] == "1.0"
        assert result["exam_id"] == "E001"
        assert result["subject"] == "生物"
        assert "image_size" in result
        assert "anchors" in result
        assert "regions" in result

    def test_anchors_paperseg_format(self, sample_skeleton_and_layout):
        skeleton, layout = sample_skeleton_and_layout
        result = skeleton_to_paperseg_json(skeleton, layout, "E001", "生物")
        for a in result["anchors"]:
            assert "id" in a
            assert "cx" in a and "cy" in a
            assert "x" in a and "y" in a
            assert "w" in a and "h" in a

    def test_regions_include_all_types(self, sample_skeleton_and_layout):
        skeleton, layout = sample_skeleton_and_layout
        result = skeleton_to_paperseg_json(skeleton, layout, "E001", "生物")
        types = {r["type"] for r in result["regions"]}
        assert "choice_group" in types
        assert "subjective" in types

    def test_all_rects_valid(self, sample_skeleton_and_layout):
        skeleton, layout = sample_skeleton_and_layout
        result = skeleton_to_paperseg_json(skeleton, layout, "E001", "生物")
        for r in result["regions"]:
            rect = r["rect"]
            assert rect["x1"] < rect["x2"]
            assert rect["y1"] < rect["y2"]
            assert rect["x1"] >= 0 and rect["y1"] >= 0
