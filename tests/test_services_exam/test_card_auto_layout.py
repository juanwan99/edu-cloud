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


# ── 共享污染防线（2026-06-11 cardtpl-pack2）──
# _load_layout 是 auto-layout（router.auto_layout_card / parse_answers v2）与
# AI card_layout 工具的共同读取入口；生物 generic 污染识别必须在该层
# fail-closed，canonical 默认必须 deepcopy 隔离模块级缓存。

import copy
import json

from edu_cloud.modules.card.layout_helpers import (
    _load_layout, _save_layout, is_biology_generic_pollution,
)
from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout


POLLUTED_CONFIG = {
    "subjectTitle": "生物", "paperSize": "A4",
    "choiceCount": 11, "fillCount": 3, "essayCount": 5,
}


def _polluted_layout() -> dict:
    """前端 createDefaultLayout 兜底形状：A4 双面各 1 列，11选择/3填空。"""
    return {
        "paper": "A4",
        "config": dict(POLLUTED_CONFIG),
        "sides": [
            {"side": "A", "columns": [{"col": 0, "regions": []}]},
            {"side": "B", "columns": [{"col": 0, "regions": []}]},
        ],
    }


@pytest.fixture
def layout_dir(tmp_path, monkeypatch):
    """隔离 editor_layouts 目录，避免读写真实保存文件。"""
    import edu_cloud.modules.card.layout_helpers as lh
    monkeypatch.setattr(lh, "_EDITOR_LAYOUT_DIR", tmp_path)
    return tmp_path


class TestBiologyGenericPollutionFingerprint:
    """五维指纹判定：全命中才为 True，任一维不符即放行。"""

    def test_full_fingerprint_match_is_true(self):
        assert is_biology_generic_pollution(_polluted_layout(), POLLUTED_CONFIG, "生物") is True

    def test_subject_name_alone_triggers_without_subject_title(self):
        """config 缺 subjectTitle 时，科目名=生物 仍触发识别。"""
        config = {k: v for k, v in POLLUTED_CONFIG.items() if k != "subjectTitle"}
        layout = _polluted_layout()
        layout["config"] = dict(config)
        assert is_biology_generic_pollution(layout, config, "生物") is True

    def test_non_biology_subject_not_matched(self):
        config = {**POLLUTED_CONFIG, "subjectTitle": "化学"}
        assert is_biology_generic_pollution(_polluted_layout(), config, "化学") is False

    def test_a3_paper_not_matched(self):
        layout = _polluted_layout()
        layout["paper"] = "A3"
        config = {**POLLUTED_CONFIG, "paperSize": "A3"}
        assert is_biology_generic_pollution(layout, config, "生物") is False

    def test_multicolumn_sides_not_matched(self):
        layout = _polluted_layout()
        layout["sides"] = [
            {"side": "A", "columns": [{"col": i, "regions": []} for i in range(3)]},
            {"side": "B", "columns": [{"col": i, "regions": []} for i in range(3)]},
        ]
        assert is_biology_generic_pollution(layout, POLLUTED_CONFIG, "生物") is False

    @pytest.mark.parametrize("key,value", [("choiceCount", 16), ("fillCount", 0)])
    def test_count_dimensions_not_matched(self, key, value):
        config = {**POLLUTED_CONFIG, key: value}
        assert is_biology_generic_pollution(_polluted_layout(), config, "生物") is False


class TestLoadLayoutPollutionGuard:
    """_load_layout 读取侧防线：污染/损坏 → canonical 默认。"""

    def _write(self, layout_dir, data):
        (layout_dir / "s1_sub1.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def test_polluted_saved_layout_falls_back_to_canonical(self, layout_dir):
        self._write(layout_dir, {
            "layout": _polluted_layout(), "config": dict(POLLUTED_CONFIG), "choices": [],
        })
        layout = _load_layout("s1", "sub1", "生物")
        assert layout["paper"] == "A3"
        assert layout["config"]["choiceCount"] == 16
        assert layout["config"]["fillCount"] == 0

    def test_legitimate_saved_layout_returned_as_is(self, layout_dir):
        legitimate = _polluted_layout()
        legitimate["config"] = {**POLLUTED_CONFIG, "choiceCount": 16, "fillCount": 0}
        self._write(layout_dir, {
            "layout": legitimate, "config": dict(legitimate["config"]), "choices": [],
        })
        layout = _load_layout("s1", "sub1", "生物")
        assert layout["paper"] == "A4"
        assert layout["config"]["choiceCount"] == 16

    def test_missing_file_returns_canonical_default(self, layout_dir):
        layout = _load_layout("s1", "sub1", "生物")
        assert layout["paper"] == "A3"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 3]

    def test_corrupt_file_falls_back_to_canonical(self, layout_dir):
        (layout_dir / "s1_sub1.json").write_text("{not valid json", encoding="utf-8")
        layout = _load_layout("s1", "sub1", "生物")
        assert layout["paper"] == "A3"

    def test_missing_layout_key_falls_back_to_canonical(self, layout_dir):
        self._write(layout_dir, {"config": dict(POLLUTED_CONFIG), "choices": []})
        layout = _load_layout("s1", "sub1", "生物")
        assert layout["paper"] == "A3"

    def test_default_fallback_is_deepcopy_isolated_from_cache(self, layout_dir):
        """回退返回值被调用方原地修改（_apply_to_regions）不得污染模块缓存。"""
        baseline = copy.deepcopy(get_default_layout("生物"))

        layout = _load_layout("s1", "sub1", "生物")
        layout["config"]["choiceCount"] = -999
        layout["sides"][0]["columns"][0]["regions"].append({"id": "intruder", "type": "essay"})

        fresh = get_default_layout("生物")
        assert fresh["config"]["choiceCount"] == baseline["config"]["choiceCount"]
        assert fresh["sides"][0]["columns"][0]["regions"] == baseline["sides"][0]["columns"][0]["regions"]

    def test_polluted_fallback_is_deepcopy_isolated_from_cache(self, layout_dir):
        self._write(layout_dir, {
            "layout": _polluted_layout(), "config": dict(POLLUTED_CONFIG), "choices": [],
        })
        baseline = copy.deepcopy(get_default_layout("生物"))

        layout = _load_layout("s1", "sub1", "生物")
        layout["config"]["choiceCount"] = -999

        assert get_default_layout("生物")["config"]["choiceCount"] == baseline["config"]["choiceCount"]


class TestAutoLayoutChainPollutionGuard:
    """auto-layout 全链路（_load_layout → calculate_layout → _apply_to_regions →
    _save_layout）：污染 saved 文件不得在排版回写后存活。"""

    PARSED = [
        {"qno": 17, "total_score": 12,
         "subs": [{"sub": 1, "answers": ["光合作用产生氧气"]}]},
        {"qno": 18, "total_score": 12,
         "subs": [{"sub": 1, "answers": ["细胞质"]}, {"sub": 2, "answers": ["线粒体"]}]},
    ]

    def test_polluted_saved_does_not_survive_auto_layout_roundtrip(self, layout_dir):
        (layout_dir / "s1_sub1.json").write_text(
            json.dumps({
                "layout": _polluted_layout(), "config": dict(POLLUTED_CONFIG), "choices": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        layout = _load_layout("s1", "sub1", "生物")
        result = calculate_layout(self.PARSED, layout.get("config"), existing_layout=layout)
        layout = _apply_to_regions(layout, result)
        _save_layout("s1", "sub1", layout)

        saved = json.loads((layout_dir / "s1_sub1.json").read_text(encoding="utf-8"))
        assert saved["layout"]["paper"] == "A3", "generic A4 形状不得在 auto-layout 回写后存活"
        assert saved["config"]["choiceCount"] == 16
        assert saved["config"]["fillCount"] == 0

    def test_auto_layout_roundtrip_does_not_pollute_default_cache(self, layout_dir):
        """回写链路基于 deepcopy 操作，模块缓存中的学科默认保持不变。"""
        baseline = copy.deepcopy(get_default_layout("生物"))

        layout = _load_layout("s1", "sub1", "生物")
        result = calculate_layout(self.PARSED, layout.get("config"), existing_layout=layout)
        layout = _apply_to_regions(layout, result)
        _save_layout("s1", "sub1", layout)

        fresh = get_default_layout("生物")
        assert fresh == baseline, "auto-layout 回写不得污染 subject_defaults._LAYOUT_CACHE"


def _underscore_keys(value, path=""):
    """递归收集下划线前缀 key 的路径列表。"""
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.startswith("_"):
                found.append(f"{path}/{k}")
            found.extend(_underscore_keys(v, f"{path}/{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found.extend(_underscore_keys(v, f"{path}[{i}]"))
    return found


class TestSaveLayoutRuntimeFieldStrip:
    """保存链路运行时字段剥离契约（2026-06-11 cardtpl-pack3）。

    _side/_col/_sideIdx 等下划线前缀字段由前端 render.js 渲染时注入、或由
    TQL/SUBJECT_CONFIGS 生成器携带，仅服务当次渲染交互；editor_layouts
    持久层必须与 canonical 资产同等净化（见 TestCanonicalAssetHygiene），
    _save_layout 是 auto-layout / parse-answers v2 / AI card_layout 的
    共用写入口。
    """

    def _dirty_layout(self) -> dict:
        return {
            "paper": "A3",
            "config": {"subjectTitle": "物理", "choiceCount": 10},
            "sides": [
                {"side": "A", "columns": [
                    {"col": 0, "regions": [
                        {"id": "header", "type": "fixed", "role": "header",
                         "_side": "A", "_col": 0, "_sideIdx": 0},
                        {"id": "essay-11", "type": "essay", "qno": 11, "score": 6,
                         "heightRatio": 1.0, "subs": [],
                         "_side": "A", "_col": 0, "_sideIdx": 0, "_height_mm": 42.5},
                    ]},
                ]},
            ],
        }

    def test_strip_runtime_render_fields_recursive_and_pure(self):
        """递归剥离所有下划线前缀 key；合法字段保留；不修改入参。"""
        from edu_cloud.modules.card.layout_helpers import strip_runtime_render_fields
        dirty = self._dirty_layout()
        snapshot = copy.deepcopy(dirty)

        cleaned = strip_runtime_render_fields(dirty)

        assert _underscore_keys(cleaned) == []
        essay = cleaned["sides"][0]["columns"][0]["regions"][1]
        assert essay["qno"] == 11
        assert essay["score"] == 6
        assert essay["heightRatio"] == 1.0
        assert dirty == snapshot, "净化必须返回新结构，不得修改入参"

    def test_save_layout_strips_runtime_fields(self, layout_dir):
        """_save_layout 落盘文件递归无任何下划线前缀 key。"""
        _save_layout("s1", "sub1", self._dirty_layout())

        saved = json.loads((layout_dir / "s1_sub1.json").read_text(encoding="utf-8"))
        assert _underscore_keys(saved) == []
        regions = saved["layout"]["sides"][0]["columns"][0]["regions"]
        assert [r["id"] for r in regions] == ["header", "essay-11"]

    def test_auto_layout_roundtrip_persists_no_runtime_fields(self, layout_dir):
        """物理默认布局（SUBJECT_CONFIGS fallback，自带 _side/_col/_sideIdx）经
        auto-layout 全链路回写后，落盘文件递归无下划线前缀 key。"""
        parsed = [
            {"qno": 11, "total_score": 6,
             "subs": [{"sub": 1, "answers": ["匀速直线运动"]}]},
        ]
        layout = _load_layout("s1", "sub1", "物理")
        assert _underscore_keys(layout), "前置条件：物理默认布局应含运行时字段"

        result = calculate_layout(parsed, layout.get("config"), existing_layout=layout)
        layout = _apply_to_regions(layout, result)
        _save_layout("s1", "sub1", layout)

        saved = json.loads((layout_dir / "s1_sub1.json").read_text(encoding="utf-8"))
        assert _underscore_keys(saved) == []
