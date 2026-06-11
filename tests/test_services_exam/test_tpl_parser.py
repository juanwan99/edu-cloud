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


class TestCanonicalSubjectDefaults:
    """canonical_layouts/ 权威模板契约（2026-06-11 cardtpl-pack1）。

    取代原 TestTqlA4Contract：化学/英语/生物的 get_default_layout 现在优先返回
    canonical 资产，不再走 TQL。契约显式编码纸张、列结构、qcols（essay 题号
    按列分布）、choice/fill/essay 题量，防止再次退化为 generic 布局。
    """

    @staticmethod
    def _essay_qnos_by_col(layout: dict, side_idx: int) -> list[list]:
        return [
            [r["qno"] for r in col["regions"] if r.get("type") == "essay"]
            for col in layout["sides"][side_idx]["columns"]
        ]

    def test_chemistry_canonical_a4_multicolumn(self):
        """化学 = A4 多栏 [3,1]：col0 Q15 / col1 Q16 / col2 Q17+Q18，14选择/0填空/4解答。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("化学")
        assert layout["paper"] == "A4"
        assert layout["config"]["paperSize"] == "A4"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 1]
        assert self._essay_qnos_by_col(layout, 0) == [[15], [16], [17, 18]]
        assert self._essay_qnos_by_col(layout, 1) == [[]]
        cfg = layout["config"]
        assert cfg["choiceCount"] == 14
        assert cfg["fillCount"] == 0
        assert cfg["essayCount"] == 4
        assert sum(g["count"] for g in cfg["choiceGroups"]) == 14

    def test_chemistry_a_side_col0_has_fixed_regions(self):
        """化学 A 面 col0 含完整 fixed 区（header/info/notice/choices）。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("化学")
        roles = [r.get("role") for r in layout["sides"][0]["columns"][0]["regions"] if r["type"] == "fixed"]
        assert roles == ["header", "info", "notice", "choices"]

    def test_english_canonical_a4_single_column(self):
        """英语 = A4 [1,1]：55选择 + 填空56-65 + 写作两节（B 面续写第一节 + 第二节）。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("英语")
        assert layout["paper"] == "A4"
        assert [len(s["columns"]) for s in layout["sides"]] == [1, 1]
        cfg = layout["config"]
        assert cfg["choiceCount"] == 55
        assert sum(g["count"] for g in cfg["choiceGroups"]) == 55
        assert cfg["fillCount"] == 10
        assert cfg["fillStart"] == 56
        assert cfg["essayCount"] == 2
        assert cfg["essayConfig"] == [{"score": 15}, {"score": 25}]
        a_regions = layout["sides"][0]["columns"][0]["regions"]
        fill_qnos = [r["qno"] for r in a_regions if r["type"] == "fill"]
        assert fill_qnos == list(range(56, 66))
        a_essay_ids = [r["id"] for r in a_regions if r["type"] == "essay"]
        assert a_essay_ids == ["essay-Q_写作第一节"]
        b_essay_ids = [r["id"] for r in layout["sides"][1]["columns"][0]["regions"] if r["type"] == "essay"]
        assert b_essay_ids == ["essay-Q_写作第一节-cont", "essay-Q_写作第二节"]

    def test_biology_canonical_a3_three_columns(self):
        """生物（PROVISIONAL，源自候选 e1cc167b，最终 canonical 待用户确认）：
        A3 [3,3]：col0 Q17 / col1 Q18+Q19 / col2 Q20+Q21，16选择(13-16多选)/0填空/5解答。
        注：候选 ab5a1279 与 e1cc167b 形状契约相同，替换不影响本测试。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("生物")
        assert layout["paper"] == "A3"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 3]
        assert self._essay_qnos_by_col(layout, 0) == [[17], [18, 19], [20, 21]]
        assert self._essay_qnos_by_col(layout, 1) == [[], [], []]
        cfg = layout["config"]
        assert cfg["choiceCount"] == 16
        assert cfg["fillCount"] == 0
        assert cfg["essayCount"] == 5
        multi_groups = [(g["start"], g["count"]) for g in cfg["choiceGroups"] if g.get("multi")]
        assert multi_groups == [(13, 3), (16, 1)]

    def test_biology_not_generic_a4_shape(self):
        """生物默认绝不能是前端 generic 形状（A4 单栏 / 11选择 / 3填空）——污染事故指纹。"""
        from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
        layout = get_default_layout("生物")
        cfg = layout["config"]
        assert layout["paper"] != "A4"
        assert not (cfg["choiceCount"] == 11 and cfg["fillCount"] == 3)


class TestCanonicalFailClosed:
    """canonical 资产不可用 fail-closed 契约（2026-06-11 cardtpl-pack3）。

    取代 pack1 的静默 fallback 测试：已知 canonical 学科（化学/英语/生物）的
    权威模板缺失、损坏或格式不合法时必须抛 CanonicalLayoutError，禁止静默
    退回 TQL/SUBJECT_CONFIGS 泛化模板——静默降级正是 2026-06 模板劣化事故
    的根源。非 canonical 学科不受影响，仍走原 fallback 链。
    """

    @pytest.fixture
    def sd(self, monkeypatch, tmp_path):
        """隔离 canonical 目录与模块缓存，返回 (module, canonical_dir)。"""
        import edu_cloud.modules.card.rendering.subject_defaults as sd
        monkeypatch.setattr(sd, "_LAYOUT_CACHE", {})
        monkeypatch.setattr(sd, "_CANONICAL_DIR", tmp_path)
        return sd, tmp_path

    @pytest.mark.parametrize("subject", ["化学", "英语", "生物"])
    def test_canonical_missing_fails_closed(self, sd, subject):
        """canonical 文件缺失 → 抛 CanonicalLayoutError，不退泛化模板。"""
        mod, _ = sd
        with pytest.raises(mod.CanonicalLayoutError):
            mod.get_default_layout(subject)

    def test_canonical_corrupt_fails_closed(self, sd):
        """canonical 文件损坏（非法 JSON）→ 抛 CanonicalLayoutError。"""
        mod, cdir = sd
        (cdir / "canonical_chemistry.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(mod.CanonicalLayoutError):
            mod.get_default_layout("化学")

    @pytest.mark.parametrize("payload", [
        '"just a string"',                       # 顶层非 dict
        '{"config": {}}',                        # 缺 sides
        '{"config": {}, "sides": []}',           # sides 为空
        '{"config": {}, "sides": [{"side": "A"}]}',  # side 缺 columns 列表
        '{"sides": [{"side": "A", "columns": []}]}',  # 缺 config
    ])
    def test_canonical_malformed_fails_closed(self, sd, payload):
        """canonical 文件为合法 JSON 但格式不合法 → 抛 CanonicalLayoutError。"""
        mod, cdir = sd
        (cdir / "canonical_chemistry.json").write_text(payload, encoding="utf-8")
        with pytest.raises(mod.CanonicalLayoutError):
            mod.get_default_layout("化学")

    def test_non_canonical_subject_unaffected(self, sd):
        """非 canonical 学科（物理）不受 fail-closed 影响，仍走原 fallback 链。"""
        mod, _ = sd
        layout = mod.get_default_layout("物理")
        assert isinstance(layout, dict)
        assert "sides" in layout

    def test_failure_not_cached_recovers_after_repair(self, sd):
        """失败不得写入缓存：资产修复后同名学科立即恢复正常返回。"""
        mod, cdir = sd
        target = cdir / "canonical_chemistry.json"
        target.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(mod.CanonicalLayoutError):
            mod.get_default_layout("化学")

        from pathlib import Path
        real = Path(__file__).resolve().parents[2] / (
            "src/edu_cloud/modules/card/rendering/canonical_layouts/canonical_chemistry.json"
        )
        target.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
        layout = mod.get_default_layout("化学")
        assert layout["paper"] == "A4"
        assert [len(s["columns"]) for s in layout["sides"]] == [3, 1]


class TestCanonicalAssetHygiene:
    """canonical_layouts/ 资产净化契约（2026-06-11 cardtpl-pack2）。

    _side/_col/_sideIdx 等下划线前缀字段是前端渲染时注入的运行时标记，
    不得持久化进 canonical 真源资产；打包部署必须随包分发这些资产。
    """

    def test_canonical_assets_have_no_runtime_underscore_keys(self):
        """三个 canonical JSON 递归无任何下划线前缀 key。"""
        from edu_cloud.modules.card.rendering import subject_defaults as sd
        files = sorted(sd._CANONICAL_DIR.glob("canonical_*.json"))
        assert len(files) >= 3, f"canonical_layouts 资产缺失: {files}"
        for p in files:
            data = json.loads(p.read_text(encoding="utf-8"))
            bad = []

            def walk(x, path=""):
                if isinstance(x, dict):
                    for k, v in x.items():
                        if k.startswith("_"):
                            bad.append(f"{path}/{k}")
                        walk(v, f"{path}/{k}")
                elif isinstance(x, list):
                    for i, v in enumerate(x):
                        walk(v, f"{path}[{i}]")

            walk(data)
            assert not bad, f"{p.name} 含运行时字段: {bad[:10]}"

    def test_pyproject_declares_canonical_layouts_package_data(self):
        """pyproject 必须声明 canonical_layouts/*.json 为 package-data，
        否则打包部署会静默丢失 canonical 模板、学科默认退化到 fallback。"""
        import tomllib
        from pathlib import Path
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        pkg_data = data.get("tool", {}).get("setuptools", {}).get("package-data", {})
        assert any(
            "canonical_layouts/*.json" in item
            for vals in pkg_data.values() if isinstance(vals, list)
            for item in vals
        ), f"package-data 未声明 canonical_layouts/*.json: {pkg_data}"
