"""tpl 模板文件解析器 — 将外部 .tpl JSON 转换为 edu-cloud Template 格式。"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 定位点 ID 映射
_LOC_ID_MAP = {"0101": "TL", "0102": "TR", "0103": "BR", "0104": "BL"}


def _parse_tpl_location(loc_str: str) -> dict:
    """解析 tpl 坐标格式 '(x1,y1)-(x2,y2)' → {x1, y1, x2, y2}。"""
    m = re.match(r"\((\d+),(\d+)\)-\((\d+),(\d+)\)", loc_str)
    if not m:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    return {"x1": int(m[1]), "y1": int(m[2]), "x2": int(m[3]), "y2": int(m[4])}


def convert_tpl(tpl_data: dict, page: int | None = None) -> dict:
    """将 .tpl JSON 数据转换为 edu-cloud 模板格式。

    Args:
        tpl_data: 原始 .tpl JSON（含 tplInfo + datas）
        page: None=全部页, 0=A面, 1=B面

    Returns:
        {image_size, anchors[], regions[], barcode_region, tpl_name}
    """
    info = tpl_data.get("tplInfo", {})
    datas = tpl_data.get("datas", {})

    # 定位点
    anchors = []
    for loc in datas.get("tplLocsList", []):
        if page is not None and loc.get("inpage", 0) != page:
            continue
        if not loc.get("busing", True):
            continue
        loc_id = _LOC_ID_MAP.get(loc.get("loc_no", ""), loc.get("loc_name", ""))
        loc_str = loc.get("location") or loc.get("Location", "")
        if not loc_str:
            continue
        rect = _parse_tpl_location(loc_str)
        anchors.append({
            "id": loc_id,
            "x": rect["x1"], "y": rect["y1"],
            "w": rect["x2"] - rect["x1"], "h": rect["y2"] - rect["y1"],
            "cx": (rect["x1"] + rect["x2"]) // 2,
            "cy": (rect["y1"] + rect["y2"]) // 2,
        })

    # 主观题区域
    regions = []
    for i, q in enumerate(datas.get("tplSubqueList", [])):
        if page is not None and q.get("inpage", 0) != page:
            continue
        if not q.get("busing", 1):
            continue
        q_loc_str = q.get("location") or q.get("Location", "")
        if not q_loc_str:
            continue
        rect = _parse_tpl_location(q_loc_str)
        score_str = q.get("score_val", "0")
        score = int(score_str) if score_str.isdigit() else 0
        regions.append({
            "id": f"Q{i + 1:02d}",
            "name": q.get("que_name", f"题{i + 1}"),
            "type": "subjective",
            "question_type": "essay",
            "rect": rect,
            "page": q.get("inpage", 0),
            "score": score,
        })

    # 选择题组
    for i, g in enumerate(datas.get("tplObjqueGList", [])):
        if page is not None and g.get("inpage", 0) != page:
            continue
        if not g.get("busing", True):
            continue
        g_loc_str = g.get("location") or g.get("Location", "")
        if not g_loc_str:
            continue
        rect = _parse_tpl_location(g_loc_str)
        labels = [s.strip() for s in g.get("opt_symbol", "A,B,C,D").split(",")]
        is_multi = g.get("opt_type", "") == "多选"
        regions.append({
            "id": f"OBJ{i + 1:02d}",
            "name": g.get("qg_name", f"选择题组{i + 1}"),
            "type": "choice_group",
            "question_type": "multi_choice" if is_multi else "choice",
            "rect": rect,
            "page": g.get("inpage", 0),
            "score": 0,
            "cols": g.get("opt_count", 4),
            "rows": g.get("que_count", 1),
            "labels": labels,
            "multi_select": is_multi,
            "qg_indexno": g.get("qg_indexno", 1),
        })

    # 条码区域
    barcode_region = None
    for bc in datas.get("MbNoBarCodeList", []):
        if bc.get("busing", True):
            bc_loc_str = bc.get("location") or bc.get("Location", "")
            if bc_loc_str:
                barcode_region = _parse_tpl_location(bc_loc_str)
            break

    return {
        "image_size": {"width": info.get("iwidth", 0), "height": info.get("iheight", 0)},
        "anchors": anchors,
        "regions": regions,
        "barcode_region": barcode_region,
        "tpl_name": info.get("tpl_name", ""),
    }


def parse_tpl_file(path: str | Path) -> dict:
    """解析 .tpl 文件并返回模板数据。"""
    with open(str(path), "r", encoding="utf-8") as f:
        tpl_data = json.load(f)
    result = convert_tpl(tpl_data)
    logger.info("parse_tpl_file: %s → %d anchors, %d regions",
                path, len(result["anchors"]), len(result["regions"]))
    return result
