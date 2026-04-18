"""finalize_skeleton 单元测试。"""
import pytest
from edu_cloud.modules.card.rendering.layout import build_skeleton_from_spec


class TestFinalizeSkeletonBasic:
    """基础链式计算测试。"""

    def _make_skeleton(self, **kwargs):
        """构造包含选择题+填空题+解答题的标准骨架。"""
        questions = []
        # 6 单选
        for i in range(1, 7):
            questions.append({"number": i, "question_type": "single_choice",
                              "options_count": 4, "score": 2})
        # 4 填空
        for i in range(7, 11):
            questions.append({"number": i, "question_type": "fill_in_blank",
                              "score": 5})
        # 3 解答
        for i in range(11, 14):
            questions.append({"number": i, "question_type": "short_answer",
                              "score": 10})
        return build_skeleton_from_spec(
            questions, paper_size="A3", columns=3,
            exam_number_digits=8, **kwargs,
        )

    def test_finalize_returns_hints(self):
        """finalize_skeleton 返回 header/notice/absent 的 mm 中间值。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        hints = finalize_skeleton(skeleton)
        assert "header_bottom_mm" in hints
        assert "notice_bottom_mm" in hints
        assert "absent_bottom_mm" in hints
        # 链式递增
        assert hints["notice_bottom_mm"] > hints["header_bottom_mm"]
        assert hints["absent_bottom_mm"] > hints["notice_bottom_mm"]

    def test_section_headers_monotonic(self):
        """所有 section_headers y 坐标严格递增。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        finalize_skeleton(skeleton)
        sh = skeleton["section_headers"]
        values = [sh["section1_y"], sh["section2_y"],
                  sh["fillin_title_y"], sh["essay_title_y"]]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1], \
                f"section_headers not monotonic: {values}"

    def test_objective_groups_no_overlap(self):
        """选择题组之间 y 区间无重叠。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        finalize_skeleton(skeleton)
        groups = skeleton.get("objective_groups", [])
        for i in range(len(groups) - 1):
            assert groups[i]["rect"]["y2"] <= groups[i + 1]["rect"]["y1"]

    def test_column0_y1_after_essay_title(self):
        """columns[0].y1 应在 essay_title_y 之后。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        finalize_skeleton(skeleton)
        col1 = [c for c in skeleton["columns"]
                if c.get("page", 0) == 0 and c["id"] == "col_1"][0]
        essay_title_y = skeleton["section_headers"]["essay_title_y"]
        assert col1["y1"] > essay_title_y

    def test_needs_finalize_flag_cleared(self):
        """finalize 后 _needs_finalize 标记被清除。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        assert skeleton.get("_needs_finalize") is True
        finalize_skeleton(skeleton)
        assert skeleton.get("_needs_finalize") is not True

    def test_skip_if_no_flag(self):
        """无 _needs_finalize 标记的 skeleton 不被修改。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        skeleton = self._make_skeleton()
        finalize_skeleton(skeleton)  # 第一次 finalize
        col1_y1_after = [c for c in skeleton["columns"]
                         if c.get("page", 0) == 0 and c["id"] == "col_1"][0]["y1"]
        finalize_skeleton(skeleton)  # 第二次应跳过
        col1_y1_again = [c for c in skeleton["columns"]
                         if c.get("page", 0) == 0 and c["id"] == "col_1"][0]["y1"]
        assert col1_y1_after == col1_y1_again


class TestFinalizeSkeletonEdgeCases:
    """边界情况测试。"""

    def test_no_objectives(self):
        """无选择题时 section1_y=0，其他坐标仍递增。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        questions = [
            {"number": 1, "question_type": "fill_in_blank", "score": 5},
            {"number": 2, "question_type": "short_answer", "score": 10},
        ]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        finalize_skeleton(skeleton)
        sh = skeleton["section_headers"]
        assert sh["section1_y"] == 0
        assert sh["section2_y"] > 0
        assert sh["essay_title_y"] > sh["fillin_title_y"]

    def test_no_fillins(self):
        """无填空题时 fillin_title_y=0。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        questions = [
            {"number": 1, "question_type": "single_choice",
             "options_count": 4, "score": 2},
            {"number": 2, "question_type": "short_answer", "score": 10},
        ]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        finalize_skeleton(skeleton)
        sh = skeleton["section_headers"]
        assert sh["fillin_title_y"] == 0

    def test_essays_only(self):
        """纯解答题时只有 essay_title_y 有值。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        questions = [
            {"number": 1, "question_type": "short_answer", "score": 10},
            {"number": 2, "question_type": "short_answer", "score": 15},
        ]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        finalize_skeleton(skeleton)
        sh = skeleton["section_headers"]
        assert sh["section1_y"] == 0
        assert sh["fillin_title_y"] == 0
        assert sh["essay_title_y"] > 0

    def test_mixed_single_and_multi_choice_no_overlap(self):
        """单选+多选两组选择题 y 区间互不重叠。"""
        from edu_cloud.modules.card.rendering.renderer import finalize_skeleton
        questions = []
        # 6 单选
        for i in range(1, 7):
            questions.append({"number": i, "question_type": "single_choice",
                              "options_count": 4, "score": 3})
        # 4 多选
        for i in range(7, 11):
            questions.append({"number": i, "question_type": "multi_choice",
                              "options_count": 4, "score": 4})
        # 2 解答
        for i in range(11, 13):
            questions.append({"number": i, "question_type": "short_answer",
                              "score": 10})
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        finalize_skeleton(skeleton)
        groups = skeleton.get("objective_groups", [])
        assert len(groups) >= 2, "应有单选+多选两组"
        for i in range(len(groups) - 1):
            assert groups[i]["rect"]["y2"] <= groups[i + 1]["rect"]["y1"], \
                f"group {i} bottom ({groups[i]['rect']['y2']}) overlaps group {i+1} top ({groups[i+1]['rect']['y1']})"


class TestNoFlagSkeletonRender:
    """DB/.tpl skeleton（无 _needs_finalize）直接渲染不报错。"""

    def test_render_without_finalize_flag(self):
        """无 flag 的 skeleton 直接走 render_card_v2 不报 KeyError。"""
        from edu_cloud.modules.card.rendering.renderer import render_card_v2, finalize_skeleton
        from edu_cloud.modules.card.rendering.layout import build_skeleton_from_spec, allocate_by_weights
        from edu_cloud.modules.card.parser.word_parser import compute_weights_from_text

        questions = [
            {"number": 1, "question_type": "single_choice", "options_count": 4, "score": 5},
            {"number": 2, "question_type": "short_answer", "score": 10},
        ]
        skeleton = build_skeleton_from_spec(questions, paper_size="A3", columns=3)
        finalize_skeleton(skeleton)  # flag cleared after this

        # 此时 skeleton 无 flag，模拟 DB/.tpl 路径
        assert not skeleton.get("_needs_finalize")

        weights = [{"number": 2, "weight": 1.0,
                    "parsed_structure": [{"sub": 1, "score": 10, "space_type": "essay"}]}]
        layout = allocate_by_weights(weights, skeleton["columns"])
        # 应不报错
        pdf = render_card_v2(skeleton, layout, "测试考试", "数学")
        assert len(pdf) > 1000
