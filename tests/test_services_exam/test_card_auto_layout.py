"""calculate_layout + _apply_to_regions + _extract_anchors 单元测试。"""
import pytest
from edu_cloud.modules.card.layout_helpers import (
    calculate_layout, _apply_to_regions, _extract_anchors,
    _make_blanks_for_answer, _pick_blank_width,
)


def _q(qno, score=10, subs=None):
    if subs is None:
        subs = [{"sub": 1, "answers": ["答案文本"]}]
    return {"qno": qno, "total_score": score, "subs": subs}


def _layout_with_essays(qnos_by_col, paper="A3"):
    """构建有 essay region 的测试 layout。
    qnos_by_col: {(side, col): [qno, ...]}
    """
    sides_data = {}
    for (side, col), qnos in qnos_by_col.items():
        if side not in sides_data:
            sides_data[side] = {}
        regions = []
        if side == "A" and col == 0:
            regions.append({"id": "header", "type": "fixed", "role": "header"})
            regions.append({"id": "choices", "type": "fixed", "role": "choices"})
        for qno in qnos:
            regions.append({
                "id": f"essay-Q{qno}", "type": "essay", "qno": qno,
                "score": 10, "heightRatio": 0.5,
                "subs": [{"sub": 1, "blanks": [{"w": "100%"}]}],
                "cuts": [{"id": "cut-1", "afterSub": 0}],
                "texts": [{"content": "注意事项", "x": 10, "y": 20}],
            })
        sides_data[side][col] = regions

    sides = []
    for side_name in sorted(sides_data.keys()):
        cols = []
        for ci in sorted(sides_data[side_name].keys()):
            cols.append({"col": ci, "regions": sides_data[side_name][ci]})
        sides.append({"side": side_name, "columns": cols})
    return {"paper": paper, "config": {"choiceCount": 11, "optionCount": 4}, "sides": sides}


class TestExtractAnchors:
    def test_basic(self):
        layout = _layout_with_essays({("A", 1): [12], ("A", 2): [13], ("B", 0): [14]})
        anchors = _extract_anchors(layout)
        assert anchors == {12: ("A", 1), 13: ("A", 2), 14: ("B", 0)}

    def test_empty_layout(self):
        assert _extract_anchors({}) == {}
        assert _extract_anchors({"sides": []}) == {}


class TestCalculateLayoutBasic:
    def test_no_questions(self):
        result = calculate_layout([])
        assert result["questions"] == []
        assert result["columns"] == []

    def test_single_question(self):
        result = calculate_layout([_q(12, 10)])
        assert len(result["questions"]) == 1
        assert result["questions"][0]["qno"] == 12
        assert len(result["columns"]) >= 1

    def test_config_affects_col0_capacity(self):
        """传 config 应减小 col0 可用容量（选择题占空间）。"""
        qs = [_q(i, 10) for i in range(12, 19)]
        r_no_config = calculate_layout(qs, config=None)
        r_with_config = calculate_layout(qs, config={"choiceCount": 30, "optionCount": 4})
        # 30 题选择题占很大空间，col0 应放更少 essay 题
        col0_no = next((c for c in r_no_config["columns"] if c["side"] == "A" and c["col"] == 0), None)
        col0_with = next((c for c in r_with_config["columns"] if c["side"] == "A" and c["col"] == 0), None)
        if col0_no and col0_with:
            assert len(col0_with["questions"]) <= len(col0_no["questions"])


class TestAnchorConstrainedLayout:
    def test_anchored_questions_stay_in_place(self):
        """有锚点时，已有题目保持在原始列。"""
        existing = _layout_with_essays({("A", 1): [12, 13], ("A", 2): [14, 15]})
        qs = [_q(12), _q(13), _q(14), _q(15)]
        result = calculate_layout(qs, config={"choiceCount": 11}, existing_layout=existing)

        col_map = {}
        for c in result["columns"]:
            for qno in c["questions"]:
                col_map[qno] = (c["side"], c["col"])

        assert col_map[12] == ("A", 1)
        assert col_map[13] == ("A", 1)
        assert col_map[14] == ("A", 2)
        assert col_map[15] == ("A", 2)

    def test_new_question_placed_after_anchored(self):
        """新增题目应被放到有空间的列，不在 A-col0（保持顺序）。"""
        existing = _layout_with_essays({("A", 1): [12], ("A", 2): [13]})
        qs = [_q(12), _q(13), _q(14)]
        result = calculate_layout(qs, config={"choiceCount": 11}, existing_layout=existing)

        col_map = {}
        for c in result["columns"]:
            for qno in c["questions"]:
                col_map[qno] = (c["side"], c["col"])

        assert 14 in col_map
        # Q14 不应在 A-col0（那里有 fixed 区域，空间最小）
        assert col_map[14] != ("A", 0) or col_map[14][0] != "A"


class TestBSideAllocation:
    def test_many_questions_overflow_to_b_side(self):
        """多道大题应溢出到 B 面。"""
        big_subs = [{"sub": i, "answers": ["一个很长的答案" * 5]} for i in range(1, 6)]
        qs = [_q(i, 15, subs=big_subs) for i in range(12, 22)]
        result = calculate_layout(qs, config={"choiceCount": 11})

        b_side_qnos = []
        for c in result["columns"]:
            if c["side"] == "B":
                b_side_qnos.extend(c["questions"])

        assert len(b_side_qnos) > 0, "10 道大题应有部分溢出到 B 面"

    def test_all_questions_assigned(self):
        """所有题目都必须被分配到某列。"""
        qs = [_q(i) for i in range(12, 20)]
        result = calculate_layout(qs, config={"choiceCount": 11})
        assigned = set()
        for c in result["columns"]:
            assigned.update(c["questions"])
        assert assigned == {12, 13, 14, 15, 16, 17, 18, 19}


class TestApplyToRegionsNonDestructive:
    def test_preserves_cuts_and_texts(self):
        """merge 应保留用户手调的 cuts 和 texts。"""
        layout = _layout_with_essays({("A", 1): [12]})
        layout_result = calculate_layout([_q(12)], config={"choiceCount": 11})
        merged = _apply_to_regions(layout, layout_result)

        essay_regions = []
        for side in merged["sides"]:
            for col in side["columns"]:
                for r in col["regions"]:
                    if r.get("type") == "essay" and r.get("qno") == 12:
                        essay_regions.append(r)

        assert len(essay_regions) == 1
        region = essay_regions[0]
        assert "cuts" in region, "cuts 应被保留"
        assert "texts" in region, "texts 应被保留"
        assert region["cuts"] == [{"id": "cut-1", "afterSub": 0}]

    def test_preserves_unmatched_regions(self):
        """不在答案中的手工 region 不应被丢弃。"""
        layout = _layout_with_essays({("A", 1): [12, 99]})
        layout_result = calculate_layout([_q(12)], config={"choiceCount": 11})
        merged = _apply_to_regions(layout, layout_result)

        all_qnos = set()
        for side in merged["sides"]:
            for col in side["columns"]:
                for r in col["regions"]:
                    if r.get("qno"):
                        all_qnos.add(r["qno"])

        assert 99 in all_qnos, "手工添加的 Q99 不应被丢弃"

    def test_updates_subs_and_score(self):
        """merge 应更新 subs 和 score。"""
        layout = _layout_with_essays({("A", 1): [12]})
        new_subs = [{"sub": 1, "answers": ["新答案"]}, {"sub": 2, "answers": ["第二问"]}]
        layout_result = calculate_layout([_q(12, score=20, subs=new_subs)], config={"choiceCount": 11})
        merged = _apply_to_regions(layout, layout_result)

        for side in merged["sides"]:
            for col in side["columns"]:
                for r in col["regions"]:
                    if r.get("qno") == 12:
                        assert len(r["subs"]) == 2
                        assert r["score"] == 20
                        return
        pytest.fail("Q12 not found")


class TestBlankWidth:
    def test_short_answer(self):
        # len("DNA") = 3 ≤ 8 → 30%
        assert _pick_blank_width("DNA") == "30%"

    def test_medium_answer(self):
        # len("常染色体显性遗传") = 8 ≤ 8 → 30%（按字符数，不是视觉宽度）
        assert _pick_blank_width("常染色体显性遗传") == "30%"

    def test_medium_range(self):
        # len > 8 且 ≤ 20 → 48%
        assert _pick_blank_width("常染色体显性遗传病的特征") == "48%"

    def test_long_answer(self):
        # len > 20 → 100%
        long_text = "一个很长的答案需要一整行来写完这些内容加上更多的字才能超过二十"
        assert len(long_text) > 20
        assert _pick_blank_width(long_text) == "100%"

    def test_empty_answer(self):
        assert _pick_blank_width("") == "100%"

    def test_continuation_line(self):
        # 需要超过 CHARS_PER_LINE 才会续行，100% 宽度一行 30 字符
        long_text = "一" * 35
        blanks = _make_blanks_for_answer(long_text)
        assert len(blanks) >= 2
        assert blanks[0].get("continuation") is None
        assert blanks[-1].get("continuation") is True
