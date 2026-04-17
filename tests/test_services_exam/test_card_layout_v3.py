"""layout.py v3 规则引擎测试 — allocate_by_weights()。"""
import pytest
from edu_cloud.modules.card.rendering.layout import allocate_by_weights


# --- 辅助 ---

def _make_columns(n=3, col_width=450, col_height=1000, y_start=100):
    """构造 n 栏配置。"""
    cols = []
    for i in range(n):
        x1 = 50 + i * (col_width + 20)
        cols.append({
            "id": f"col{i+1}",
            "x1": x1,
            "x2": x1 + col_width,
            "y1": y_start,
            "y2": y_start + col_height,
        })
    return cols


def _make_weights(specs):
    """specs: [(number, weight, n_subs, sub_scores)] → question_weights list。"""
    items = []
    for number, weight, n_subs, sub_scores in specs:
        parsed = []
        for i in range(n_subs):
            parsed.append({
                "sub": i + 1,
                "score": sub_scores[i] if i < len(sub_scores) else 2,
                "space_type": "fill-blank",
                "blanks": [{"content": "答案", "estimated_width_cm": 3.0}],
                "estimated_lines": 0,
            })
        items.append({
            "number": number,
            "weight": weight,
            "parsed_structure": parsed,
        })
    return items


class TestAllocateByWeights:
    def test_single_question_fills_column(self):
        """单题占满整栏。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = _make_weights([(17, 1.0, 2, [6, 6])])
        result = allocate_by_weights(weights, cols)
        assert len(result["slots"]) == 1
        slot = result["slots"][0]
        assert slot["slot_id"] == "Q17"
        # 整题矩形应占满栏高
        assert slot["final_rect"]["y1"] == cols[0]["y1"]
        assert slot["final_rect"]["y2"] == cols[0]["y2"]
        # 有 2 个 sub_regions
        assert len(slot["sub_regions"]) == 2

    def test_two_questions_proportional(self):
        """两题按权重比例分配高度。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = _make_weights([
            (17, 0.6, 2, [4, 8]),
            (18, 0.4, 1, [12]),
        ])
        result = allocate_by_weights(weights, cols)
        assert len(result["slots"]) == 2
        h17 = result["slots"][0]["final_rect"]["y2"] - result["slots"][0]["final_rect"]["y1"]
        h18 = result["slots"][1]["final_rect"]["y2"] - result["slots"][1]["final_rect"]["y1"]
        assert h17 > h18  # 0.6 > 0.4
        # 总和 = 栏高
        assert h17 + h18 == 1000

    def test_overflow_to_next_column(self):
        """第一栏放不下 → 换到第二栏。"""
        cols = _make_columns(n=2, col_height=500)
        # 4 题平均权重，min_height = 2 sub × 80px = 160px
        # 按权重每题比例分 500px，但 4 题 min 共需 640 > 500
        weights = _make_weights([
            (17, 0.25, 2, [6, 6]),
            (18, 0.25, 2, [6, 6]),
            (19, 0.25, 2, [6, 6]),
            (20, 0.25, 2, [6, 6]),
        ])
        result = allocate_by_weights(weights, cols)
        assert len(result["slots"]) == 4
        # 至少一题应在 col2 的 x 范围
        col2_x1 = cols[1]["x1"]
        in_col2 = [s for s in result["slots"] if s["final_rect"]["x1"] == col2_x1]
        assert len(in_col2) > 0

    def test_minimum_height_enforced(self):
        """小权重题不能低于 min_height（sub_count × 80px）。"""
        cols = _make_columns(n=1, col_height=2000)
        weights = _make_weights([
            (17, 0.95, 1, [10]),   # 大题
            (18, 0.05, 3, [2, 2, 2]),  # 小权重但 3 小问 → min = 240px
        ])
        result = allocate_by_weights(weights, cols)
        h18 = result["slots"][1]["final_rect"]["y2"] - result["slots"][1]["final_rect"]["y1"]
        assert h18 >= 3 * 80  # 最小 240px

    def test_all_columns_full_raises(self):
        """栏不够时抛出 ValueError。"""
        cols = _make_columns(n=1, col_height=100)
        weights = _make_weights([
            (17, 0.5, 3, [4, 4, 4]),  # min = 240 > 100
            (18, 0.5, 3, [4, 4, 4]),
        ])
        with pytest.raises(ValueError, match="空间不足"):
            allocate_by_weights(weights, cols)

    def test_single_question_exceeds_column_raises(self):
        """单题高度超过所有栏高时抛出 ValueError。"""
        cols = _make_columns(n=1, col_height=100)
        weights = _make_weights([
            (17, 1.0, 3, [4, 4, 4]),  # min = 3*120 = 360 > 100
        ])
        with pytest.raises(ValueError, match="空间不足"):
            allocate_by_weights(weights, cols)

    def test_no_overlap(self):
        """同栏内任意两题矩形 y 不重叠。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = _make_weights([
            (17, 0.33, 2, [6, 6]),
            (18, 0.33, 2, [6, 6]),
            (19, 0.34, 2, [6, 6]),
        ])
        result = allocate_by_weights(weights, cols)
        rects = [s["final_rect"] for s in result["slots"]]
        for i in range(len(rects) - 1):
            assert rects[i]["y2"] <= rects[i + 1]["y1"]

    def test_no_gaps(self):
        """同栏内相邻题矩形 y 连续（无缝隙）。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = _make_weights([
            (17, 0.5, 2, [6, 6]),
            (18, 0.5, 2, [6, 6]),
        ])
        result = allocate_by_weights(weights, cols)
        rects = [s["final_rect"] for s in result["slots"]]
        for i in range(len(rects) - 1):
            assert rects[i]["y2"] == rects[i + 1]["y1"]

    def test_sub_regions_score_proportional(self):
        """题内 sub_regions 按 sub_score 比例分配高度。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = _make_weights([(17, 1.0, 3, [2, 6, 4])])
        result = allocate_by_weights(weights, cols)
        srs = result["slots"][0]["sub_regions"]
        h1 = srs[0]["rect"]["y2"] - srs[0]["rect"]["y1"]
        h2 = srs[1]["rect"]["y2"] - srs[1]["rect"]["y1"]
        h3 = srs[2]["rect"]["y2"] - srs[2]["rect"]["y1"]
        # h2 (score=6) 应 > h3 (score=4) > h1 (score=2)
        assert h2 > h3 > h1

    def test_blanks_positioned(self):
        """fill-blank 类型的 blank 横线有坐标和合理宽度。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = [{
            "number": 17,
            "weight": 1.0,
            "parsed_structure": [{
                "sub": 1, "score": 6,
                "space_type": "fill-blank",
                "blanks": [
                    {"content": "基因突变", "estimated_width_cm": 3.5},
                    {"content": "常染色体显性遗传", "estimated_width_cm": 7.0},
                ],
                "estimated_lines": 0,
            }],
        }]
        result = allocate_by_weights(weights, cols)
        sr = result["slots"][0]["sub_regions"][0]
        assert len(sr["blanks"]) == 2
        for b in sr["blanks"]:
            assert b["width"] > 0
            assert b["x"] >= sr["rect"]["x1"]
            assert b["x"] + b["width"] <= sr["rect"]["x2"]

    def test_essay_lines(self):
        """essay 类型产出 estimated_lines 条水平引导线。"""
        cols = _make_columns(n=1, col_height=1000)
        weights = [{
            "number": 17,
            "weight": 1.0,
            "parsed_structure": [{
                "sub": 1, "score": 10,
                "space_type": "essay",
                "blanks": [],
                "estimated_lines": 5,
            }],
        }]
        result = allocate_by_weights(weights, cols)
        sr = result["slots"][0]["sub_regions"][0]
        assert sr.get("type") == "essay"
        assert sr.get("line_count", 0) >= 5
