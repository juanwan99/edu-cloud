"""统一渲染器测试。"""
import pytest
from edu_cloud.modules.card.renderer import render_card_v2, DEFAULT_STYLE


@pytest.fixture
def codegen_skeleton():
    """代码生成的 skeleton（无 subjective_slots、无 tpl_images）。"""
    from edu_cloud.modules.card.layout import build_skeleton_from_spec
    qs = [
        {"number": 1, "question_type": "single_choice", "options_count": 4, "score": 2},
        {"number": 2, "question_type": "single_choice", "options_count": 4, "score": 2},
        {"number": 3, "question_type": "short_answer", "score": 10,
         "answer_text": "测试答案" * 10, "image_count": 0, "weight": 0.5},
        {"number": 4, "question_type": "short_answer", "score": 15,
         "answer_text": "测试答案" * 30, "image_count": 1, "weight": 0.5},
    ]
    return build_skeleton_from_spec(qs, paper_size="A3", columns=3)


@pytest.fixture
def codegen_layout(codegen_skeleton):
    from edu_cloud.modules.card.layout import allocate_by_weights
    weights = [
        {"number": 3, "weight": 0.4,
         "parsed_structure": [{"sub": 1, "score": 10, "space_type": "essay", "estimated_lines": 0}]},
        {"number": 4, "weight": 0.6,
         "parsed_structure": [{"sub": 1, "score": 15, "space_type": "essay", "estimated_lines": 0}]},
    ]
    return allocate_by_weights(weights, codegen_skeleton["columns"])


class TestDefaultStyle:
    def test_default_style_has_required_keys(self):
        assert "title_font_size" in DEFAULT_STYLE
        assert "bracket_w_mm" in DEFAULT_STYLE
        assert "writing_line_gap_mm" in DEFAULT_STYLE


class TestUnifiedRenderer:
    def test_renders_pdf_bytes(self, codegen_skeleton, codegen_layout):
        pdf = render_card_v2(codegen_skeleton, codegen_layout, "测试考试", "生物")
        assert isinstance(pdf, bytes)
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 1000

    def test_renders_with_custom_style(self, codegen_skeleton, codegen_layout):
        style = {"font_size_title": 20, "bubble_radius_mm": 3.0}
        pdf = render_card_v2(codegen_skeleton, codegen_layout, "测试考试", "生物", style=style)
        assert isinstance(pdf, bytes)
        assert pdf[:5] == b"%PDF-"

    def test_no_tpl_images_still_renders(self, codegen_skeleton, codegen_layout):
        """没有 tpl_images 时应走代码生成路径，不报错。"""
        assert "tpl_images" not in codegen_skeleton
        pdf = render_card_v2(codegen_skeleton, codegen_layout, "测试考试", "生物")
        assert len(pdf) > 1000


class TestNewComponents:
    def test_render_with_exam_number(self):
        """含考号涂卡区的完整渲染。"""
        from edu_cloud.modules.card.layout import build_skeleton_from_spec, allocate_by_weights
        qs = [
            {"number": 1, "question_type": "single_choice", "options_count": 4, "score": 2},
            {"number": 2, "question_type": "short_answer", "score": 10,
             "answer_text": "答案", "image_count": 0, "weight": 1.0},
        ]
        skel = build_skeleton_from_spec(qs, paper_size="A3", columns=3, exam_number_digits=8)
        weights = [{"number": 2, "weight": 1.0,
                    "parsed_structure": [{"sub": 1, "score": 10, "space_type": "essay", "estimated_lines": 0}]}]
        layout = allocate_by_weights(weights, skel["columns"])
        pdf = render_card_v2(skel, layout, "期中考试", "物理",
                             style={"show_exam_number": True})
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 2000

    def test_render_without_notice(self, codegen_skeleton, codegen_layout):
        pdf = render_card_v2(codegen_skeleton, codegen_layout, "测试", "数学",
                             style={"show_notice": False})
        assert pdf[:5] == b"%PDF-"
