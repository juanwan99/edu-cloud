"""tpl_parser 单元测试。"""
import json
import os
import pytest
from edu_cloud.modules.card.tpl_parser import parse_tpl_file


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

    def test_page1_offset(self, minimal_tpl):
        """inpage=1 的主观题 x 坐标应加 page_width 偏移。"""
        result = parse_tpl_file(minimal_tpl)
        slots = result["subjective_slots"]
        page_width = result["page_width"]
        # 第 3 个槽 (19题) 是 inpage=1
        q19 = [s for s in slots if s["slot_id"] == "Q19"][0]
        assert q19["rect"]["x1"] >= page_width  # 偏移后 x1 >= 1654

    def test_columns_inferred(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        cols = result["columns"]
        assert len(cols) >= 2  # A3 至少 2 栏
        for col in cols:
            assert "id" in col
            assert "x1" in col
            assert "x2" in col

    def test_source_dpi(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        dpi = result["source_dpi"]
        # A3 展开 420mm, image_width=3308 → dpi ≈ 200
        assert 190 <= dpi <= 210

    def test_paper_size(self, minimal_tpl):
        result = parse_tpl_file(minimal_tpl)
        assert result["paper_size"] == "A3"
        assert result["image_width"] == 1654 * 2
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
        assert bio_skeleton["paper_size"] == "A3"
        assert bio_skeleton["image_width"] > 0
        assert bio_skeleton["image_height"] > 0
