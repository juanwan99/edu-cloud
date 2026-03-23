"""build_skeleton_from_spec() 测试。"""
import pytest
from edu_cloud.modules.card.layout import build_skeleton_from_spec

# --- 常量 ---
# A3 @200dpi: 3308×2339, A4 @200dpi: 1654×2339


class TestPaperSpec:
    def test_a3_dimensions(self):
        skeleton = build_skeleton_from_spec([], paper_size="A3")
        assert skeleton["image_width"] == 3308
        assert skeleton["image_height"] == 2339
        assert skeleton["source_dpi"] == 200

    def test_a4_dimensions(self):
        skeleton = build_skeleton_from_spec([], paper_size="A4")
        assert skeleton["image_width"] == 1654
        assert skeleton["image_height"] == 2339


class TestAnchors:
    def test_four_anchors_generated(self):
        skeleton = build_skeleton_from_spec([], paper_size="A3")
        anchors = skeleton["anchors"]
        assert len(anchors) == 4
        ids = {a["id"] for a in anchors}
        assert ids == {"TL", "TR", "BL", "BR"}

    def test_anchor_area_within_paperseg_constraints(self):
        """paper-seg 要求: 面积 800-8000px², 长宽比 0.5-2.5"""
        skeleton = build_skeleton_from_spec([], paper_size="A3")
        for a in skeleton["anchors"]:
            r = a["rect"]
            w = r["x2"] - r["x1"]
            h = r["y2"] - r["y1"]
            area = w * h
            assert 800 <= area <= 8000, f"Anchor {a['id']} area={area} out of range"
            ratio = w / h
            assert 0.5 <= ratio <= 2.5, f"Anchor {a['id']} ratio={ratio} out of range"

    def test_anchors_at_corners(self):
        skeleton = build_skeleton_from_spec([], paper_size="A3")
        img_w, img_h = skeleton["image_width"], skeleton["image_height"]
        for a in skeleton["anchors"]:
            r = a["rect"]
            cx = (r["x1"] + r["x2"]) / 2
            cy = (r["y1"] + r["y2"]) / 2
            if a["id"] == "TL":
                assert cx < img_w * 0.1 and cy < img_h * 0.1
            elif a["id"] == "TR":
                assert cx > img_w * 0.9 and cy < img_h * 0.1
            elif a["id"] == "BR":
                assert cx > img_w * 0.9 and cy > img_h * 0.9
            elif a["id"] == "BL":
                assert cx < img_w * 0.1 and cy > img_h * 0.9


def _bio_questions():
    """模拟生物试卷：6 单选 + 5 不定项 + 5 主观题。"""
    qs = []
    for i in range(1, 7):
        qs.append({"number": i, "question_type": "single_choice", "options_count": 4, "score": 2})
    for i in range(7, 12):
        qs.append({"number": i, "question_type": "multi_choice", "options_count": 4, "score": 3})
    for i in range(12, 17):
        qs.append({"number": i, "question_type": "short_answer", "score": 8,
                   "answer_text": "测试答案" * 20, "image_count": 0, "weight": 0.2})
    return qs


class TestObjectiveGroups:
    def test_single_and_multi_grouped_separately(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3")
        groups = skeleton["objective_groups"]
        assert len(groups) == 2
        single = [g for g in groups if not g.get("multi_select")]
        multi = [g for g in groups if g.get("multi_select")]
        assert len(single) == 1
        assert single[0]["count"] == 6
        assert single[0]["start_no"] == 1
        assert len(multi) == 1
        assert multi[0]["count"] == 5
        assert multi[0]["start_no"] == 7

    def test_objective_group_rect_valid(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3")
        for g in skeleton["objective_groups"]:
            r = g["rect"]
            assert r["x1"] < r["x2"]
            assert r["y1"] < r["y2"]
            assert r["x1"] >= 0 and r["y1"] >= 0

    def test_no_objectives_produces_empty_groups(self):
        qs = [{"number": 1, "question_type": "short_answer", "score": 10,
               "answer_text": "答案", "image_count": 0, "weight": 1.0}]
        skeleton = build_skeleton_from_spec(qs, paper_size="A3")
        assert skeleton["objective_groups"] == []


class TestColumns:
    def test_three_columns_a3(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3", columns=3)
        cols = skeleton["columns"]
        assert len(cols) == 6  # 3 front + 3 back (双面)
        front_cols = [c for c in cols if c.get("page", 0) == 0]
        assert len(front_cols) == 3
        # 第 1 栏 y1 应该在选择题底部之下
        # 第 2、3 栏 y1 应该在锚点之下
        assert front_cols[0]["y1"] > front_cols[1]["y1"]  # col1 留了选择题空间

    def test_two_columns_a4(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A4", columns=2)
        cols = skeleton["columns"]
        assert len(cols) == 4  # 2 front + 2 back (双面)

    def test_columns_no_overlap(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3", columns=3)
        # 同页内的栏不应重叠
        for page in [0, 1]:
            page_cols = sorted(
                [c for c in skeleton["columns"] if c.get("page", 0) == page],
                key=lambda c: c["x1"],
            )
            for i in range(len(page_cols) - 1):
                assert page_cols[i]["x2"] <= page_cols[i + 1]["x1"], "Columns overlap"

    def test_columns_fill_page_height(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3", columns=3)
        img_h = skeleton["image_height"]
        for col in skeleton["columns"]:
            assert col["y2"] <= img_h
            assert col["y2"] > img_h * 0.8  # 应接近页面底部

    def test_column_coords_positive(self):
        skeleton = build_skeleton_from_spec(_bio_questions(), paper_size="A3", columns=3)
        for col in skeleton["columns"]:
            assert col["x1"] >= 0
            assert col["y1"] >= 0
            assert col["x1"] < col["x2"]
            assert col["y1"] < col["y2"]


class TestExamNumber:
    def test_exam_number_digits_stored(self):
        skeleton = build_skeleton_from_spec(
            _bio_questions(), paper_size="A3", exam_number_digits=8,
        )
        assert skeleton.get("exam_number_digits") == 8

    def test_no_exam_number_when_zero(self):
        skeleton = build_skeleton_from_spec(
            _bio_questions(), paper_size="A3", exam_number_digits=0,
        )
        assert skeleton.get("exam_number_digits") is None


class TestEndToEnd:
    def test_bio_exam_full_skeleton(self):
        """完整的生物试卷骨架：6单选 + 5不定项 + 5主观。"""
        skeleton = build_skeleton_from_spec(
            _bio_questions(), paper_size="A3", columns=3, exam_number_digits=8,
        )
        assert len(skeleton["anchors"]) == 4
        assert len(skeleton["objective_groups"]) == 2
        assert len(skeleton["columns"]) == 6  # 3 front + 3 back
        assert skeleton.get("exam_number_digits") == 8

    def test_skeleton_compatible_with_allocate(self):
        """生成的 skeleton.columns 可直接喂给 allocate_by_weights()。"""
        from edu_cloud.modules.card.layout import allocate_by_weights
        qs = _bio_questions()
        skeleton = build_skeleton_from_spec(qs, paper_size="A3", columns=3)
        subjectives = [q for q in qs if q["question_type"] == "short_answer"]
        weights = [{"number": q["number"], "weight": q["weight"],
                    "parsed_structure": [{"sub": 1, "score": q["score"],
                                          "space_type": "essay", "estimated_lines": 0}]}
                   for q in subjectives]
        layout = allocate_by_weights(weights, skeleton["columns"])
        assert len(layout["slots"]) == len(subjectives)
