"""TQL 渲染器单元测试。"""
import pytest
from edu_cloud.modules.card.layout import build_skeleton_from_spec, allocate_by_weights
from edu_cloud.modules.card.renderer import render_card_v2


def _make_yuwen_fixture():
    """22 道语文题 fixture（与 seed 数据一致）。"""
    questions = []
    # 5 单选
    for i in range(1, 6):
        questions.append({"number": i, "question_type": "single_choice",
                          "options_count": 4, "score": 3})
    # 1 多选
    questions.append({"number": 6, "question_type": "multi_choice",
                      "options_count": 7, "score": 5})
    # 16 主观题
    subj_scores = [6, 6, 8, 8, 6, 6, 10, 10, 6, 6, 8, 8, 6, 6, 8, 60]
    for i, score in enumerate(subj_scores, start=7):
        questions.append({"number": i, "question_type": "essay",
                          "score": score, "answer_text": "答案" * (score // 2),
                          "image_count": 0})
    return questions


def _render_yuwen():
    """渲染语文答题卡，返回 (pdf_bytes, skeleton, layout)。"""
    questions = _make_yuwen_fixture()
    skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
    weights = [{"number": q["number"], "weight": q.get("score", 1),
                "parsed_structure": [{"sub": 1, "score": q.get("score", 1),
                                      "space_type": "essay", "estimated_lines": 0}]}
               for q in questions if q["question_type"] == "essay"]
    layout = allocate_by_weights(weights, skeleton["columns"])
    pdf = render_card_v2(skeleton, layout, "2024年秋季高二检测卷", "语文")
    return pdf, skeleton, layout


class TestTQLRendererSmoke:
    def test_renders_valid_pdf(self):
        """渲染完整语文答题卡，输出合法 PDF 且有实际内容（>20KB）。

        阈值 20KB 保证 PDF 非空白（纯空 ~6KB）。字体跨平台差异：
        Windows SimHei ~30KB / Linux Droid Sans Fallback ~25KB。
        """
        pdf, _, _ = _render_yuwen()
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 20_000, f"PDF too small: {len(pdf)} bytes"

    def test_no_objective_questions(self):
        """0 道选择题不应抛异常。"""
        questions = [{"number": 1, "question_type": "essay",
                      "score": 60, "answer_text": "作文" * 50, "image_count": 0}]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        weights = [{"number": 1, "weight": 60,
                    "parsed_structure": [{"sub": 1, "score": 60,
                                          "space_type": "essay", "estimated_lines": 0}]}]
        layout = allocate_by_weights(weights, skeleton["columns"])
        pdf = render_card_v2(skeleton, layout, "期中考试", "语文")
        assert pdf[:5] == b"%PDF-"

    def test_no_subjective_questions(self):
        """0 道主观题不应抛异常。"""
        questions = [{"number": i, "question_type": "single_choice",
                      "options_count": 4, "score": 3} for i in range(1, 11)]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        layout = allocate_by_weights([], skeleton["columns"])
        pdf = render_card_v2(skeleton, layout, "期中考试", "语文")
        assert pdf[:5] == b"%PDF-"


class TestTQLVisualOutput:
    def test_generate_yuwen_pdf_to_disk(self):
        """生成语文答题卡 PDF 到 test_output/ 供人工比对。"""
        import os
        pdf, _, _ = _render_yuwen()
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "tql_yuwen_a3.pdf")
        with open(out_path, "wb") as f:
            f.write(pdf)
        assert os.path.getsize(out_path) > 20_000
        print(f"\n✅ TQL 语文答题卡已生成: {os.path.abspath(out_path)}")
        print(f"   文件大小: {len(pdf):,} bytes")
        print(f"   请与 docs/reference/tql/[141984001]语文_p1.png 人工比对")
