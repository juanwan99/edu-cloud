"""解析月小二 .tpl 模板文件为 CardSkeleton 数据。

.tpl 文件为 JSON 格式，实际结构：
- tplInfo: 模板元信息（iwidth/iheight 为单页像素尺寸）
- datas: 包含定位点、客观题组、主观题区域等
  - tplLocsList: 定位点（loc_no, location 字符串）
  - tplObjqueGList: 客观题组（qg_indexno=起始题号, que_count, opt_count, location）
  - tplSubqueList: 主观题区域（que_name=题号, location, score_val, inpage）
- images: 模板图片（base64）

注意：部分字符串字段为 GBK 编码被 JSON 按 latin-1 存储，需要 encode('latin1').decode('gbk') 修复。
"""
from __future__ import annotations
import json
import re
from pathlib import Path


# .tpl anchor loc_no → 标准 id 映射
_ANCHOR_MAP = {"0101": "TL", "0102": "TR", "0103": "BR", "0104": "BL"}

# 纸张物理宽度 (mm)
_A3_WIDTH_MM = 420.0
_A4_WIDTH_MM = 210.0


def _decode_gbk(s: str) -> str:
    """尝试修复 GBK 编码被 latin-1 读取的字符串。"""
    if not s:
        return s
    try:
        return s.encode("latin1").decode("gbk")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _parse_location(loc_str: str) -> dict:
    """解析 '(x1,y1)-(x2,y2)' 格式的位置字符串。"""
    m = re.match(r"\((\d+),(\d+)\)-\((\d+),(\d+)\)", loc_str.strip())
    if not m:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    return {
        "x1": int(m.group(1)),
        "y1": int(m.group(2)),
        "x2": int(m.group(3)),
        "y2": int(m.group(4)),
    }


def parse_tpl_file(path: str | Path) -> dict:
    """解析 .tpl 文件，返回骨架 JSON。"""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        tpl = json.load(f)

    info = tpl.get("tplInfo", {})
    datas = tpl.get("datas", {})

    # iwidth 可能是 A4 半页宽度（~1654px@200dpi）或 A3 全展开宽度（~3308px@200dpi）
    page_width = info.get("iwidth", 0)
    page_height = info.get("iheight", 0)

    # 检测是否有 inpage=1 的主观题（正反两面）
    subj_raw = datas.get("tplSubqueList", [])
    has_page1 = any(s.get("inpage", 0) == 1 for s in subj_raw)

    # 判断纸张规格
    if page_width <= 2000 and has_page1:
        # A4 双面：每面独立坐标，不拼接
        image_width = page_width
        paper_size = "A4"
    elif page_width <= 2000:
        # A4 单面（无 B 面 slot）→ 按 A3 展开处理（向后兼容）
        image_width = page_width * 2
        paper_size = "A3"
    else:
        # iwidth 已是 A3 全展开宽度
        image_width = page_width
        paper_size = "A3"
    image_height = page_height

    paper_width_mm = _A4_WIDTH_MM if paper_size == "A4" else _A3_WIDTH_MM

    # 推算 DPI
    source_dpi = round(image_width * 25.4 / paper_width_mm) if image_width > 0 else 200

    # 解析定位点
    anchors = _parse_anchors(datas.get("tplLocsList", []))

    # 解析客观题组
    objective_groups = _parse_objective_groups(datas.get("tplObjqueGList", []))

    # 解析主观题区域（subj_raw 已在上方 has_page1 检测时读取）
    is_a4_dual = paper_size == "A4" and has_page1
    subjective_slots = _parse_subjective_slots(subj_raw, page_width, is_a4_dual=is_a4_dual)

    # 推断栏定义：A4 双面时只用 page0 推断；A3 全展开也只用 page0
    page0_only = paper_size == "A4" or page_width > 2000
    columns = _infer_columns(subjective_slots, image_width, page0_only=page0_only)
    # 回填 columns 到 slots
    for slot in subjective_slots:
        slot["columns"] = _find_columns(
            slot["rect"]["x1"], slot["rect"]["x2"], columns
        )

    # 提取模板背景图（base64 PNG）
    tpl_images = _extract_images(tpl)

    return {
        "paper_size": paper_size,
        "is_a4_dual": is_a4_dual,
        "image_width": image_width,
        "image_height": image_height,
        "page_width": page_width,
        "source_dpi": source_dpi,
        "anchors": anchors,
        "objective_groups": objective_groups,
        "columns": columns,
        "subjective_slots": subjective_slots,
        "tpl_images": tpl_images,
    }


def _parse_anchors(locs_list: list) -> list[dict]:
    """解析定位点列表。"""
    anchors = []
    for loc in locs_list:
        loc_no = str(loc.get("loc_no", ""))
        std_id = _ANCHOR_MAP.get(loc_no, loc_no)
        rect = _parse_location(loc.get("location", ""))
        anchors.append({
            "id": std_id,
            "rect": rect,
        })
    return anchors


def _parse_objective_groups(obj_list: list) -> list[dict]:
    """解析客观题组列表。"""
    groups = []
    for g in obj_list:
        opt_type_raw = _decode_gbk(g.get("opt_type", ""))
        is_multi = "多选" in opt_type_raw or "多" in opt_type_raw
        rect = _parse_location(g.get("location", ""))
        groups.append({
            "group_id": f"{'多选' if is_multi else '单选'}{len(groups) + 1}",
            "start_no": g.get("qg_indexno", 1),
            "count": g.get("que_count", 0),
            "options": g.get("opt_count", 4),
            "symbols": g.get("opt_symbol", "A,B,C,D"),
            "multi_select": is_multi,
            "rect": rect,
        })
    return groups


def _parse_subjective_slots(subj_list: list, page_width: int, *, is_a4_dual: bool = False) -> list[dict]:
    """解析主观题区域为槽位列表。

    inpage=0 的区域坐标属于第一页，inpage=1 属于第二页。
    A4 单面拼 A3 时 inpage=1 的 x 坐标加 page_width 偏移；
    A4 双面时各面独立坐标，不偏移。
    """
    slots = []
    # A4 单面拼 A3 时需要 x 偏移；A4 双面和 A3 全展开都不偏移
    # is_a4_dual=True 表示 A4 双面，各面独立坐标
    needs_x_offset = page_width <= 2000 and not is_a4_dual
    for s in subj_list:
        que_name = s.get("que_name", "")
        inpage = s.get("inpage", 0)
        rect = _parse_location(s.get("location", ""))

        # A4 半页模板：inpage=1 的 x 坐标加 page_width 偏移（拼成 A3 展开图）
        if inpage == 1 and needs_x_offset:
            rect["x1"] += page_width
            rect["x2"] += page_width

        # que_name 可能已含"题"（如 "4题"），避免重复
        if que_name:
            label = que_name if "题" in que_name else f"{que_name}题"
        else:
            label = _decode_gbk(s.get("que_type", ""))
        slot_id = _extract_slot_id(que_name or label)

        score_val = s.get("score_val", "0")
        try:
            score = float(score_val)
        except (ValueError, TypeError):
            score = 0

        slots.append({
            "slot_id": slot_id,
            "label": label,
            "columns": [],  # filled in later by caller
            "rect": rect,
            "height_flexible": True,
            "score": score,
            "inpage": inpage,
        })

    # 作文题标记 height_flexible=False
    for slot in slots:
        if "作文" in slot["label"]:
            slot["height_flexible"] = False

    return slots


def _infer_columns(
    slots: list[dict], image_width: int, *, page0_only: bool = False
) -> list[dict]:
    """从主观题 x 坐标聚类推算栏定义。

    Args:
        page0_only: True 时只用 inpage=0 的 slots（A3 全展开模板，背面独立坐标）
    """
    if page0_only:
        use_slots = [s for s in slots if s.get("inpage", 0) == 0]
    else:
        use_slots = slots
    if not use_slots:
        return []

    x1_values = sorted(set(s["rect"]["x1"] for s in use_slots))
    if not x1_values:
        return []

    threshold = image_width * 0.2
    clusters: list[list[int]] = [[x1_values[0]]]
    for x in x1_values[1:]:
        if x - clusters[-1][-1] > threshold:
            clusters.append([x])
        else:
            clusters[-1].append(x)

    columns = []
    for i, cluster in enumerate(clusters):
        x1_min = min(cluster)
        x2_max = 0
        y1_min = float("inf")
        y2_max = 0
        for s in use_slots:
            sx = s["rect"]["x1"]
            if sx in cluster:
                x2_max = max(x2_max, s["rect"]["x2"])
                y1_min = min(y1_min, s["rect"]["y1"])
                y2_max = max(y2_max, s["rect"]["y2"])
        columns.append({
            "id": f"col{i + 1}",
            "x1": x1_min,
            "x2": x2_max,
            "y1": int(y1_min) if y1_min != float("inf") else 0,
            "y2": y2_max,
        })

    return columns


def _find_columns(x1: int, x2: int, columns: list[dict]) -> list[str]:
    """判断区域跨越哪些栏。"""
    result = []
    for col in columns:
        if x1 < col["x2"] and x2 > col["x1"]:
            result.append(col["id"])
    return result or ([columns[0]["id"]] if columns else [])


def _extract_images(tpl: dict) -> dict[int, str]:
    """提取模板背景图（base64 PNG），按 inpage 索引。

    Returns:
        {0: "base64...", 1: "base64..."} — page 0 和 page 1 的背景图
    """
    images_raw = tpl.get("images", [])
    result: dict[int, str] = {}
    for img in images_raw:
        inpage = img.get("inpage", 0)
        b64 = img.get("img_picture", "")
        if b64 and inpage not in result:
            result[inpage] = b64
    return result


def _extract_slot_id(label: str) -> str:
    """从标签提取 slot_id，如 '17题' → 'Q17', '17' → 'Q17'。"""
    match = re.search(r"(\d+)", label)
    if match:
        return f"Q{match.group(1)}"
    return f"Q_{label}"
