"""扫描模块 tpl 模板文件解析测试。"""
import pytest


FAKE_TPL = {
    "tplInfo": {"iwidth": 3299, "iheight": 2289, "tpl_name": "地理"},
    "datas": {
        "tplLocsList": [
            {"loc_no": "0101", "location": "(67,71)-(125,112)", "inpage": 0, "busing": True, "loc_name": "1页左上"},
            {"loc_no": "0102", "location": "(1121,73)-(1179,115)", "inpage": 0, "busing": True, "loc_name": "1页右上"},
            {"loc_no": "0103", "location": "(1116,2189)-(1174,2230)", "inpage": 0, "busing": True, "loc_name": "1页右下"},
            {"loc_no": "0104", "location": "(64,2187)-(122,2228)", "inpage": 0, "busing": True, "loc_name": "1页左下"},
        ],
        "tplSubqueList": [
            {"que_no": "07001", "que_name": "17题(1)", "location": "(88,1015)-(1169,1677)", "inpage": 0, "score_val": "6", "busing": 1, "que_type": "解答题"},
            {"que_no": "07002", "que_name": "17题(2)", "location": "(93,1579)-(1174,2192)", "inpage": 0, "score_val": "4", "busing": 1, "que_type": "解答题"},
        ],
        "tplObjqueGList": [
            {"qg_no": "06001", "qg_name": "单选", "location": "(161,833)-(384,935)", "opt_count": 4, "que_count": 5, "opt_symbol": "A,B,C,D", "inpage": 0, "qg_indexno": 1, "direction": "纵向排列"},
        ],
        "MbNoBarCodeList": [
            {"bc_no": "0310", "bc_name": "条码考号", "location": "(678,231)-(1175,509)", "inpage": 0, "busing": True},
        ],
        "tplUnexamList": [
            {"unexam_no": "0401", "unexam_name": "缺考标识", "location": "(932,650)-(962,667)", "inpage": 0, "busing": True, "iwidth": 31, "iheight": 18},
        ],
    },
}


class TestParseLocation:
    def test_parse_normal(self):
        from edu_cloud.modules.scan.tpl_parser import _parse_tpl_location
        result = _parse_tpl_location("(88,1015)-(1169,1677)")
        assert result == {"x1": 88, "y1": 1015, "x2": 1169, "y2": 1677}

    def test_parse_zero(self):
        from edu_cloud.modules.scan.tpl_parser import _parse_tpl_location
        result = _parse_tpl_location("(0,0)-(0,0)")
        assert result == {"x1": 0, "y1": 0, "x2": 0, "y2": 0}

    def test_parse_invalid(self):
        from edu_cloud.modules.scan.tpl_parser import _parse_tpl_location
        result = _parse_tpl_location("invalid")
        assert result == {"x1": 0, "y1": 0, "x2": 0, "y2": 0}


class TestConvertTpl:
    def test_anchors(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert len(result["anchors"]) == 4
        ids = {a["id"] for a in result["anchors"]}
        assert ids == {"TL", "TR", "BR", "BL"}
        tl = next(a for a in result["anchors"] if a["id"] == "TL")
        assert tl["cx"] == (67 + 125) // 2
        assert tl["cy"] == (71 + 112) // 2

    def test_subjective_regions(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        subj = [r for r in result["regions"] if r["type"] == "subjective"]
        assert len(subj) == 2
        assert subj[0]["name"] == "17题(1)"
        assert subj[0]["rect"] == {"x1": 88, "y1": 1015, "x2": 1169, "y2": 1677}
        assert subj[0]["score"] == 6

    def test_objective_regions(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        obj = [r for r in result["regions"] if r["type"] == "choice_group"]
        assert len(obj) == 1
        assert obj[0]["cols"] == 4
        assert obj[0]["rows"] == 5
        assert obj[0]["labels"] == ["A", "B", "C", "D"]

    def test_image_size(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert result["image_size"] == {"width": 3299, "height": 2289}

    def test_barcode_region(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert result["barcode_region"] == {"x1": 678, "y1": 231, "x2": 1175, "y2": 509}


class TestParseTplFile:
    @pytest.mark.skipif(
        not __import__("os").path.exists(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl"),
        reason="Real tpl file not available",
    )
    def test_parse_real_tpl(self):
        from edu_cloud.modules.scan.tpl_parser import parse_tpl_file
        result = parse_tpl_file(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl")
        assert len(result["anchors"]) == 4
        subj = [r for r in result["regions"] if r["type"] == "subjective"]
        assert len(subj) == 10  # 地理 10 个主观题区域
