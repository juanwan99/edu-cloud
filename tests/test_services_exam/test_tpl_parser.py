"""tpl_parser 单元测试。"""
import json
import os
import pytest
from edu_cloud.modules.card.rendering.tpl_parser import parse_tpl_file


# 真实 .tpl 文件路径
TPL_DIR = "D:/试卷数据/YueXiaoEr/Scanner/Templetes"
BIO_TPL = f"{TPL_DIR}/[188993007]生物.tpl"

# 跳过条件：真实文件不存在时
skip_no_tpl = pytest.mark.skipif(
    not os.path.exists(BIO_TPL),
    reason=f"真实 .tpl 文件不存在: {BIO_TPL}",
)


@pytest.fixture
def bio_skeleton():
    return parse_tpl_file(BIO_TPL)


@pytest.fixture
def minimal_tpl(tmp_path):
    """创建最小 .tpl JSON 用于无外部依赖的测试。"""
    tpl_data = {
        "tplInfo": {"iwidth": 1654, "iheight": 2283, "ipages": 1},
        "datas": {
            "tplLocsList": [
                {"loc_no": "0101", "location": "(114,92)-(178,123)", "busing": True},
                {"loc_no": "0102", "location": "(1476,92)-(1540,123)", "busing": True},
                {"loc_no": "0103", "location": "(1479,2185)-(1543,2216)", "busing": True},
                {"loc_no": "0104", "location": "(114,2185)-(178,2216)", "busing": True},
            ],
            "tplObjqueGList": [
                {
                    "qg_indexno": 1, "que_count": 4, "opt_count": 4,
                    "opt_symbol": "A,B,C,D", "opt_type": "单选",
                    "location": "(185,825)-(411,964)",
                },
                {
                    "qg_indexno": 13, "que_count": 4, "opt_count": 4,
                    "opt_symbol": "A,B,C,D", "opt_type": "多选",
                    "location": "(1281,825)-(1507,964)",
                },
            ],
            "tplSubqueList": [
                {"que_name": "17", "location": "(101,1048)-(1568,1749)", "inpage": 0, "score_val": "12"},
                {"que_name": "18", "location": "(101,1693)-(1562,2188)", "inpage": 0, "score_val": "12"},
                {"que_name": "19", "location": "(98,117)-(1565,854)", "inpage": 1, "score_val": "12"},
                {"que_name": "20", "location": "(108,789)-(1565,1523)", "inpage": 1, "score_val": "12"},
                {"que_name": "21", "location": "(94,1457)-(1575,2191)", "inpage": 1, "score_val": "12"},
            ],
        },
        "images": [],
    }
    fp = tmp_path / "test.tpl"
    fp.write_text(json.dumps(tpl_data), encoding="utf-8")
    return fp


class TestMinimalTpl:
    """使用最小伪造 .tpl 文件，不依赖外部文件。"""

    def test_parse_returns_dict(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        assert isinstance(result, dict)

    def test_anchors(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        anchors = result["anchors"]
        assert len(anchors) == 4
        ids = {a["id"] for a in anchors}
        assert ids == {"TL", "TR", "BR", "BL"}
        for a in anchors:
            assert "rect" in a
            rect = a["rect"]
            assert all(k in rect for k in ("x1", "y1", "x2", "y2"))

    def test_objective_groups(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        groups = result["objective_groups"]
        assert len(groups) == 2
        assert groups[0]["start_no"] == 1
        assert groups[0]["count"] == 4
        assert groups[0]["multi_select"] is False
        assert groups[1]["multi_select"] is True

    def test_subjective_slots(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        slots = result["subjective_slots"]
        assert len(slots) == 5
        labels = [s["label"] for s in slots]
        assert "17题" in labels
        for s in slots:
            assert "slot_id" in s
            assert "columns" in s
            assert "rect" in s
            assert "height_flexible" in s

    def test_a4_dual_no_offset(self, minimal_tpl):
        """A4 双面模板：inpage=1 的 x 坐标不偏移，保持原始值。"""
        result = parse_tpl_file(minimal_tpl)
        assert result["is_a4_dual"] is True
        assert result["paper_size"] == "A4"
        slots = result["subjective_slots"]
        q19 = [s for s in slots if s["slot_id"] == "Q19"][0]
        # A4 双面不偏移，x1 保持原始值（< page_width）
        assert q19["rect"]["x1"] < result["page_width"]

    def test_columns_inferred(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        cols = result["columns"]
        # A4 双面只有 1 栏（page0 的 slot 全在同一栏）
        assert len(cols) >= 1
        for col in cols:
            assert "id" in col
            assert "x1" in col
            assert "x2" in col

    def test_source_dpi(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        dpi = result["source_dpi"]
        # A4 双面: image_width=1654, 210mm → dpi ≈ 200
        assert 190 <= dpi <= 210

    def test_paper_size(self, minimal_tpl):
        """A4 双面模板：paper_size=A4，image_width=单页宽。"""
        result = parse_tpl_file(minimal_tpl)
        assert result["paper_size"] == "A4"
        assert result["image_width"] == 1654  # A4 双面不翻倍
        assert result["image_height"] == 2283


@skip_no_tpl
class TestRealTpl:
    """使用真实 .tpl 文件。"""

    def test_parse_returns_dict(self, bio_skeleton):
        assert isinstance(bio_skeleton, dict)

    def test_anchors(self, bio_skeleton):
        anchors = bio_skeleton["anchors"]
        assert len(anchors) == 4
        ids = {a["id"] for a in anchors}
        assert ids == {"TL", "TR", "BR", "BL"}

    def test_objective_groups(self, bio_skeleton):
        groups = bio_skeleton["objective_groups"]
        assert len(groups) >= 3
        for g in groups:
            assert "start_no" in g
            assert "count" in g
            assert "options" in g
            assert "multi_select" in g
            assert "rect" in g

    def test_subjective_slots(self, bio_skeleton):
        slots = bio_skeleton["subjective_slots"]
        assert len(slots) == 5
        labels = [s["label"] for s in slots]
        assert "17题" in labels
        for s in slots:
            assert "slot_id" in s
            assert "columns" in s
            assert "rect" in s
            assert "height_flexible" in s

    def test_source_dpi(self, bio_skeleton):
        dpi = bio_skeleton["source_dpi"]
        assert 190 <= dpi <= 210

    def test_paper_size(self, bio_skeleton):
        # [188993007]生物 iwidth=1654 + 有 page1 slot = A4 双面
        assert bio_skeleton["paper_size"] == "A4"
        assert bio_skeleton["is_a4_dual"] is True
        assert bio_skeleton["image_width"] > 0
        assert bio_skeleton["image_height"] > 0


class TestSubjectDefaults:
    """A4 layout 契约测试。"""

    def test_a4_layout_single_column_per_side(self):
        """A4 布局每面只有 1 个 column。"""
        from edu_cloud.modules.card.rendering.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        assert layout["paper"] == "A4"
        for side in layout["sides"]:
            assert len(side["columns"]) == 1, f"Side {side['side']} should have 1 column"
            assert side["columns"][0]["col"] == 0

    def test_a4_side_a_has_fixed_and_essay(self):
        """A4 A面 col 0 同时包含 fixed 和 essay regions。"""
        from edu_cloud.modules.card.rendering.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        side_a = layout["sides"][0]
        regions = side_a["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" in types, "A面 col 0 应包含 fixed regions"
        assert "essay" in types, "A面 col 0 应包含 essay regions"

    def test_a4_side_b_no_fixed(self):
        """A4 B面不包含 fixed regions。"""
        from edu_cloud.modules.card.rendering.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["英语"])
        config["subjectTitle"] = "英语"
        layout = _fallback_layout(config)
        side_b = layout["sides"][1]
        regions = side_b["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" not in types, "B面不应包含 fixed regions"

    def test_a4_chemistry_layout(self):
        """化学也是 A4 双面（14 选择 + 4 解答跨面）。"""
        from edu_cloud.modules.card.rendering.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        config = dict(SUBJECT_CONFIGS["化学"])
        config["subjectTitle"] = "化学"
        layout = _fallback_layout(config)
        paper = layout["paper"]
        for side in layout["sides"]:
            for col in side["columns"]:
                for r in col["regions"]:
                    if r.get("type") == "essay":
                        assert "heightRatio" in r

    def test_a3_subjects_unaffected(self):
        """A3 科目布局不受影响：3 栏结构。"""
        from edu_cloud.modules.card.rendering.subject_defaults import _fallback_layout, SUBJECT_CONFIGS
        for name in ["数学", "物理", "生物", "历史", "政治", "地理"]:
            config = dict(SUBJECT_CONFIGS[name])
            config["subjectTitle"] = name
            layout = _fallback_layout(config)
            assert layout["paper"] == "A3", f"{name} should be A3"
            assert len(layout["sides"][0]["columns"]) >= 2, f"{name} A面 should have ≥2 columns"


@skip_no_tpl
class TestTqlA4Contract:
    """TQL 转换路径的 A4 契约测试（需要真实 .tpl 文件）。[F02 修复]"""

    def test_tql_english_a4_single_column(self):
        """TQL 英语模板转换后也满足 A4 单 column 契约。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        assert layout["paper"] == "A4"
        for side in layout["sides"]:
            assert len(side["columns"]) == 1, f"Side {side['side']} should have 1 column"

    def test_tql_english_a_side_has_fixed_and_essay(self):
        """TQL 英语 A 面 col 0 同时含 fixed + essay。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        regions = layout["sides"][0]["columns"][0]["regions"]
        types = [r["type"] for r in regions]
        assert "fixed" in types
        assert "essay" in types

    def test_tql_chemistry_a4_contract(self):
        """TQL 化学模板转换后满足 A4 契约。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("化学")
        if layout["paper"] == "A4":
            for side in layout["sides"]:
                assert len(side["columns"]) == 1

    def test_tql_essay_config_matches_count(self):
        """TQL 英语: essayConfig 长度 == essayCount（A+B 面）。[F003 修复]"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        config = layout["config"]
        assert len(config["essayConfig"]) == config["essayCount"], \
            f"essayConfig({len(config['essayConfig'])}) != essayCount({config['essayCount']})"
