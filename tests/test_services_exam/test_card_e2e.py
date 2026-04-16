"""答题卡代码生成引擎端到端测试。"""
import pytest
from edu_cloud.modules.card.layout import build_skeleton_from_spec, allocate_by_weights
from edu_cloud.modules.card.renderer import render_card_v2
from edu_cloud.modules.card.export import skeleton_to_paperseg_json
from edu_cloud.modules.card.word_parser import compute_weights_from_text


class TestEndToEndPipeline:
    def test_bio_exam_full_pipeline(self):
        """生物试卷完整流水线：题目 → skeleton → weights → layout → PDF + JSON。"""
        # 1. 模拟题目列表（6单选 + 5不定项 + 5解答）
        questions = []
        for i in range(1, 7):
            questions.append({"number": i, "question_type": "single_choice",
                              "options_count": 4, "score": 2})
        for i in range(7, 12):
            questions.append({"number": i, "question_type": "multi_choice",
                              "options_count": 4, "score": 3})
        answers = [
            {"number": 12, "answer_text": "短答案", "image_count": 0},
            {"number": 13, "answer_text": "中等长度答案" * 5, "image_count": 0},
            {"number": 14, "answer_text": "长答案需要很多空间" * 15, "image_count": 1},
            {"number": 15, "answer_text": "较长答案" * 10, "image_count": 0},
            {"number": 16, "answer_text": "最长的答案" * 20, "image_count": 2},
        ]
        for a in answers:
            questions.append({"number": a["number"], "question_type": "short_answer",
                              "score": 8, **a})

        # 2. 生成骨架
        skeleton = build_skeleton_from_spec(
            questions, paper_size="A3", columns=3, exam_number_digits=8,
        )
        assert len(skeleton["anchors"]) == 4
        assert len(skeleton["objective_groups"]) == 2
        assert len(skeleton["columns"]) == 6  # 3 front + 3 back

        # 2b. 精化坐标
        from edu_cloud.modules.card.renderer import finalize_skeleton
        hints = finalize_skeleton(skeleton)
        assert hints.get("header_bottom_mm", 0) > 0

        # 验证坐标递增、无重叠
        sh = skeleton["section_headers"]
        active_ys = [v for v in [sh["section1_y"], sh["section2_y"],
                                  sh["essay_title_y"]] if v > 0]
        for i in range(len(active_ys) - 1):
            assert active_ys[i] < active_ys[i + 1]

        # 3. 计算权重
        weights_raw = compute_weights_from_text(answers)
        weights = []
        for w in weights_raw:
            weights.append({
                "number": w["number"],
                "weight": w["weight"],
                "parsed_structure": [{"sub": 1, "score": 8,
                                      "space_type": "essay", "estimated_lines": 0}],
            })

        # 4. 分配布局
        layout = allocate_by_weights(weights, skeleton["columns"])
        assert len(layout["slots"]) == 5

        # 5. 渲染 PDF
        pdf = render_card_v2(skeleton, layout, "2026年春季期中考试", "生物")
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 5000

        # 6. 导出切割 JSON
        tpl_json = skeleton_to_paperseg_json(skeleton, layout, "E001", "生物")
        assert len(tpl_json["anchors"]) == 4
        assert len(tpl_json["regions"]) > 0

        # 7. 验证切割 JSON 满足 paper-seg 约束
        for a in tpl_json["anchors"]:
            area = a["w"] * a["h"]
            assert 800 <= area <= 8000, f"Anchor {a['id']} area={area}"
        for r in tpl_json["regions"]:
            rect = r["rect"]
            assert rect["x1"] < rect["x2"]
            assert rect["y1"] < rect["y2"]

    def test_weight_affects_layout(self):
        """权重不同的题目应获得不同高度。"""
        questions = [
            {"number": 1, "question_type": "essay", "score": 5,
             "answer_text": "短", "image_count": 0},
            {"number": 2, "question_type": "essay", "score": 15,
             "answer_text": "长答案需要很多很多空间" * 30, "image_count": 2},
        ]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        weights_raw = compute_weights_from_text([
            {"number": 1, "answer_text": "短", "image_count": 0},
            {"number": 2, "answer_text": "长答案需要很多很多空间" * 30, "image_count": 2},
        ])
        weights = [{"number": w["number"], "weight": w["weight"],
                    "parsed_structure": [{"sub": 1, "score": 10,
                                          "space_type": "essay", "estimated_lines": 0}]}
                   for w in weights_raw]
        layout = allocate_by_weights(weights, skeleton["columns"])

        # Q2（长答案）应比 Q1（短答案）获得更大区域
        slots = {s["slot_id"]: s for s in layout["slots"]}
        q1_h = slots["Q1"]["final_rect"]["y2"] - slots["Q1"]["final_rect"]["y1"]
        q2_h = slots["Q2"]["final_rect"]["y2"] - slots["Q2"]["final_rect"]["y1"]
        assert q2_h > q1_h, f"Q2 height {q2_h} should be > Q1 height {q1_h}"
