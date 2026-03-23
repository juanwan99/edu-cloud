"""答题卡布局引擎 — 坐标工具 + 纸张定义 + 区域计算。"""
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REFERENCE_DPI = 300


def mm_to_px(mm: float, dpi: int = REFERENCE_DPI) -> int:
    """毫米转像素（参考 DPI）。"""
    return round(mm * dpi / 25.4)


def mm_to_pt(mm: float) -> float:
    """毫米转 PDF 点（1pt = 1/72 inch）。"""
    return mm * 72 / 25.4


@dataclass
class PaperSpec:
    """纸张规格。"""
    width_mm: float
    height_mm: float
    name: str


PAPER_A4 = PaperSpec(210, 297, "A4")
PAPER_A3_HALF = PaperSpec(210, 297, "A3")  # A3 对折后每面


# --- v3: AI 权重 → 精确坐标 ---

LINE_HEIGHT_PX = 35       # essay 引导线行高
MIN_HEIGHT_PER_SUB = 120  # 每小问最小高度 (px)，~15mm @200dpi，够写 3-4 行
LABEL_RESERVE_PX = 30     # 题号标签预留高度 (px)
BLANK_LEFT_MARGIN = 100   # blank 横线左边距 (题号空间)


def _cm_to_px(cm: float) -> int:
    """厘米转像素 @300DPI。"""
    return round(cm * 300 / 2.54)


def allocate_by_weights(
    question_weights: list[dict],
    columns: list[dict],
    *,
    min_height_per_sub: int = MIN_HEIGHT_PER_SUB,
) -> dict:
    """v3 规则引擎：将 AI 权重分配为精确像素坐标。

    Args:
        question_weights: AI 输出的 question_weights 列表
        columns: 栏配置 [{id, x1, x2, y1, y2}, ...]
        min_height_per_sub: 每小问最小高度 (px)

    Returns:
        layout JSON: {"slots": [...]}

    Raises:
        ValueError: 所有栏都放不下
    """
    if not question_weights:
        logger.debug("allocate_by_weights: no weights, returning empty")
        return {"slots": []}

    # 按题号排序
    sorted_qs = sorted(question_weights, key=lambda q: q["number"])

    # 计算每题最小高度 — 按分值比例动态调整
    # 高分大题（≥15分）需要更多空间，低分小题不需要 70mm 那么高
    ESSAY_MIN_HIGH = 550   # ≥15分大题: ~70mm @200dpi
    ESSAY_MIN_MED = 350    # 8-14分中题: ~45mm @200dpi
    ESSAY_MIN_LOW = 200    # <8分小题: ~25mm @200dpi
    min_heights = {}
    for q in sorted_qs:
        parsed = q.get("parsed_structure", [])
        n_subs = len(parsed)
        is_essay = any(s.get("space_type") == "essay" for s in parsed)
        if is_essay:
            score = sum(s.get("score", 1) for s in parsed) if parsed else 1
            if score >= 15:
                base = ESSAY_MIN_HIGH
            elif score >= 8:
                base = ESSAY_MIN_MED
            else:
                base = ESSAY_MIN_LOW
        else:
            base = min_height_per_sub
        min_heights[q["number"]] = max(n_subs, 1) * base

    # 均衡装箱：按栏高度比例分配权重目标，使题目均匀分布
    col_heights = [col["y2"] - col["y1"] for col in columns]
    total_col_h = sum(col_heights)
    total_weight = sum(q["weight"] for q in sorted_qs) or 1.0

    # 每栏的权重目标 = 总权重 × (栏高 / 总高)
    col_targets = [total_weight * (h / total_col_h) for h in col_heights]

    col_groups: list[list[dict]] = []
    col_idx = 0
    q_idx = 0
    col_used_weight = 0.0

    while q_idx < len(sorted_qs):
        if col_idx >= len(columns):
            remaining = [q["number"] for q in sorted_qs[q_idx:]]
            logger.warning("allocate_by_weights: overflow — placed=%d, remaining=%d (questions %s), columns=%d",
                           q_idx, len(remaining), remaining, len(columns))
            raise ValueError("空间不足，请减少题目或调整内容")

        col = columns[col_idx]
        col_h = col_heights[col_idx]
        target = col_targets[col_idx]
        group: list[dict] = []
        used_h = 0

        while q_idx < len(sorted_qs):
            q = sorted_qs[q_idx]
            min_h = min_heights[q["number"]]

            # 物理空间不足 → 必须换栏
            if used_h + min_h > col_h and group:
                break
            if used_h + min_h > col_h and not group:
                # 单题超过栏高 → 尝试下一栏（可能更高）
                # 如果已是最后一栏，后续迭代会触发 ValueError
                break

            # 权重目标已超额且已有题目 → 换栏（确保每栏至少 1 题）
            remaining_qs = len(sorted_qs) - q_idx
            remaining_cols = len(columns) - col_idx
            if (col_used_weight + q["weight"] > target * 1.15
                    and group and remaining_qs > remaining_cols):
                break

            group.append(q)
            used_h += min_h
            col_used_weight += q["weight"]
            q_idx += 1

        col_groups.append(group)
        col_idx += 1
        col_used_weight = 0.0

    # 对每栏内的题目按权重分配高度
    slots = []
    for gi, group in enumerate(col_groups):
        col = columns[gi]
        col_h = col["y2"] - col["y1"]
        total_weight = sum(q["weight"] for q in group) or 1.0
        total_min = sum(min_heights[q["number"]] for q in group)

        # 可分配的额外空间
        extra = max(0, col_h - total_min)

        y_cursor = col["y1"]
        for i, q in enumerate(group):
            min_h = min_heights[q["number"]]
            if i == len(group) - 1:
                # 最后一题填满栏底（保证无缝隙）
                h = col["y2"] - y_cursor
            else:
                # min_height + 按权重分配的额外空间
                h = min_h + int(extra * (q["weight"] / total_weight))

            slot = _build_slot(q, col, y_cursor, h, page=col.get("page", 0))
            slots.append(slot)
            y_cursor += h

    return {"slots": slots}


def _build_slot(q: dict, col: dict, y_start: int, height: int, page: int = 0) -> dict:
    """构建单题的 slot（含 sub_regions）。"""
    x1, x2 = col["x1"], col["x2"]
    final_rect = {"x1": x1, "y1": y_start, "x2": x2, "y2": y_start + height}

    qtype = q.get("question_type", "essay")
    parsed = q.get("parsed_structure", [])
    if not parsed:
        # 无解析结构 → 整个 slot 作为单个区域
        region_type = "fill_blank" if qtype == "fill_blank" else "essay"
        return {
            "slot_id": f"Q{q['number']}",
            "question_type": qtype,
            "inpage": page,
            "final_rect": final_rect,
            "sub_regions": [{
                "id": f"Q{q['number']}_1",
                "name": str(q["number"]),
                "score": q.get("weight", 1),
                "rect": dict(final_rect),
                "type": region_type,
            }],
        }

    # sub_regions 按 score 比例分配高度
    total_score = sum(s.get("score", 1) for s in parsed) or 1
    sub_regions = []
    sy = y_start

    for i, sub in enumerate(parsed):
        score = sub.get("score", 1)
        if i == len(parsed) - 1:
            sh = (y_start + height) - sy  # 最后一个填满
        else:
            sh = int(height * score / total_score)

        sr = {
            "id": f"Q{q['number']}_{sub['sub']}",
            "name": f"{q['number']}({sub['sub']})",
            "score": score,
            "rect": {"x1": x1, "y1": sy, "x2": x2, "y2": sy + sh},
        }

        space_type = sub.get("space_type", "essay")
        if space_type == "fill-blank" and sub.get("blanks"):
            sr["blanks"] = _position_blanks(sub["blanks"], x1, x2, sy)
        elif space_type == "essay":
            sr["type"] = "essay"
            lines = sub.get("estimated_lines", 0)
            if lines == 0:
                lines = max(1, (sh - LABEL_RESERVE_PX) // LINE_HEIGHT_PX)
            sr["line_count"] = lines

        sub_regions.append(sr)
        sy += sh

    return {
        "slot_id": f"Q{q['number']}",
        "question_type": qtype,
        "inpage": page,
        "final_rect": final_rect,
        "sub_regions": sub_regions,
    }


def _position_blanks(
    blanks: list[dict], x1: int, x2: int, y_start: int,
) -> list[dict]:
    """计算 blank 横线坐标。"""
    result = []
    bx = x1 + BLANK_LEFT_MARGIN
    by = y_start + LABEL_RESERVE_PX + 20

    for b in blanks:
        w = _cm_to_px(b.get("estimated_width_cm", 3.0))
        max_w = x2 - bx - 20
        w = min(w, max_w)
        w = max(w, 50)

        result.append({"x": bx, "y": by, "width": w})
        if bx + w + 50 + w < x2:
            bx = bx + w + 50
        else:
            bx = x1 + BLANK_LEFT_MARGIN
            by += 45

    return result


# --- 纸张规格 @200dpi ---
SPEC_DPI = 200

PAPER_SPECS = {
    "A3": {"width": 3308, "height": 2339},  # 420×297mm @200dpi
    "A4": {"width": 1654, "height": 2339},  # 210×297mm @200dpi
}

# 定位锚点尺寸（mm），确保面积在 paper-seg 约束 800-8000px² 内
ANCHOR_W_MM = 8.0   # 宽 8mm → @200dpi ≈ 63px
ANCHOR_H_MM = 5.0   # 高 5mm → @200dpi ≈ 39px → 面积 ≈ 2457px²
ANCHOR_MARGIN_MM = 5.0  # 距边缘 5mm


def _mm_to_px_200(mm: float) -> int:
    """毫米转像素 @200dpi。"""
    return round(mm * SPEC_DPI / 25.4)


def _generate_anchors(img_w: int, img_h: int) -> list[dict]:
    """生成 4 角定位锚点坐标。"""
    aw = _mm_to_px_200(ANCHOR_W_MM)
    ah = _mm_to_px_200(ANCHOR_H_MM)
    margin = _mm_to_px_200(ANCHOR_MARGIN_MM)

    return [
        {"id": "TL", "rect": {"x1": margin, "y1": margin, "x2": margin + aw, "y2": margin + ah}},
        {"id": "TR", "rect": {"x1": img_w - margin - aw, "y1": margin, "x2": img_w - margin, "y2": margin + ah}},
        {"id": "BR", "rect": {"x1": img_w - margin - aw, "y1": img_h - margin - ah, "x2": img_w - margin, "y2": img_h - margin}},
        {"id": "BL", "rect": {"x1": margin, "y1": img_h - margin - ah, "x2": margin + aw, "y2": img_h - margin}},
    ]


HEADER_HEIGHT_MM = 130.0  # 占位估算值，finalize_skeleton 会覆盖精确坐标
BUBBLE_ROW_HEIGHT_MM = 5.5  # 每题一行的气泡高度 — 与 renderer TQL_STYLE.bracket_row_gap_mm 对齐
BUBBLE_HEADER_MM = 6.0    # 气泡组标题行高度 — 与 renderer title_h 对齐
BUBBLE_GAP_MM = 2.0       # 组间间距 — 与 renderer +2mm 对齐
COL_MARGIN_MM = 4.0       # 栏内边距


FILLIN_ROW_HEIGHT_MM = 12.0   # 填空题每行高度（2题一行）
FILLIN_HEADER_MM = 7.0        # "二、填空题..." 标题高度
SECTION_HEADER_MM = 7.0       # "第 I 卷 选择题" 等分节标题高度


def _classify_questions(questions: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """将题目分为客观题、填空题和解答题。"""
    objective_types = {"choice", "single_choice", "multi_choice", "objective"}
    objectives = []
    fillins = []
    essays = []
    for q in sorted(questions, key=lambda x: x["number"]):
        qt = q.get("question_type", "")
        if qt in objective_types:
            objectives.append(q)
        elif qt in ("fill_blank", "fill_in_blank"):
            fillins.append(q)
        else:
            essays.append(q)
    return objectives, fillins, essays


def _build_fillin_group(
    fillins: list[dict],
    col1_x1: int, col1_x2: int,
    y_start: int,
) -> tuple[dict | None, int]:
    """构建填空题组，返回 (group_dict, y_end)。

    填空题紧凑排列：标题行 + 2题一行。
    """
    if not fillins:
        return None, y_start

    count = len(fillins)
    rows = (count + 1) // 2  # 2题一行，向上取整
    group_h_mm = FILLIN_HEADER_MM + rows * FILLIN_ROW_HEIGHT_MM + 2
    group_h = _mm_to_px_200(group_h_mm)

    group = {
        "group_id": "fill_blank",
        "rect": {"x1": col1_x1, "y1": y_start, "x2": col1_x2, "y2": y_start + group_h},
        "questions": fillins,
        "count": count,
        "start_no": fillins[0]["number"],
    }
    return group, y_start + group_h + _mm_to_px_200(BUBBLE_GAP_MM)


def _build_objective_groups(
    objectives: list[dict],
    col1_x1: int, col1_x2: int,
    y_start: int,
) -> tuple[list[dict], int]:
    """构建选择题组，返回 (groups, y_end)。

    按 question_type 分组（单选/多选独立），每组计算 rect。
    """
    if not objectives:
        return [], y_start

    groups_by_type: dict[str, list[dict]] = {}
    for q in objectives:
        qt = q["question_type"]
        is_multi = qt == "multi_choice"
        key = "multi" if is_multi else "single"
        groups_by_type.setdefault(key, []).append(q)

    result = []
    y_cursor = y_start

    for key in ["single", "multi"]:
        qs = groups_by_type.get(key, [])
        if not qs:
            continue

        count = len(qs)
        options = max(q.get("options_count", 4) for q in qs)
        start_no = qs[0]["number"]

        # 纵向布局高度：标题行 + 题号行 + options 行(ABCD) × 行间距
        row_gap = BUBBLE_ROW_HEIGHT_MM  # 5.5mm
        group_h_mm = BUBBLE_HEADER_MM + 5.0 + options * row_gap + 2
        group_h = _mm_to_px_200(group_h_mm)

        group = {
            "group_id": "不定项选择题" if key == "multi" else "单选题",
            "rect": {"x1": col1_x1, "y1": y_cursor, "x2": col1_x2, "y2": y_cursor + group_h},
            "count": count,
            "options": options,
            "start_no": start_no,
            "symbols": ",".join(chr(65 + i) for i in range(options)),
            "multi_select": key == "multi",
        }
        result.append(group)
        y_cursor += group_h + _mm_to_px_200(BUBBLE_GAP_MM)

    return result, y_cursor


EXAM_NUM_CELL_MM = 5.0   # 每个数字单元格大小
EXAM_NUM_ROWS = 10       # 0-9 十行


def _build_exam_number_area(
    digits: int, col1_x1: int, col1_x2: int, y_start: int,
) -> tuple[dict | None, int]:
    """生成考号涂卡区，返回 (area_dict, y_end)。"""
    if digits <= 0:
        return None, y_start

    cell = _mm_to_px_200(EXAM_NUM_CELL_MM)
    grid_w = digits * cell
    grid_h = EXAM_NUM_ROWS * cell
    # 居中在第 1 栏
    cx = (col1_x1 + col1_x2) // 2
    x1 = cx - grid_w // 2
    x2 = x1 + grid_w
    y2 = y_start + grid_h + _mm_to_px_200(BUBBLE_HEADER_MM)

    area = {
        "rect": {"x1": x1, "y1": y_start, "x2": x2, "y2": y2},
        "digits": digits,
    }
    return area, y2 + _mm_to_px_200(BUBBLE_GAP_MM)


def build_skeleton_from_spec(
    questions: list[dict],
    paper_size: str = "A3",
    columns: int = 3,
    style: dict | None = None,
    exam_number_digits: int = 0,
) -> dict:
    """从题目列表生成完整答题卡骨架。

    Args:
        questions: [{number, question_type, answer_text, image_count, options_count, score, weight}]
        paper_size: "A3" / "A4"
        columns: 栏数
        style: 样式覆盖
        exam_number_digits: 考号涂卡位数（0=不画）

    Returns:
        完整 skeleton dict，与 tpl_parser 输出格式兼容
    """
    obj_count = sum(1 for q in questions if q.get("question_type") == "objective")
    subj_count = sum(1 for q in questions if q.get("question_type") == "subjective")
    logger.info("build_skeleton: questions=%d (obj=%d, subj=%d), paper=%s, columns=%d",
                len(questions), obj_count, subj_count, paper_size, columns)

    spec = PAPER_SPECS.get(paper_size, PAPER_SPECS["A3"])
    img_w, img_h = spec["width"], spec["height"]

    skeleton: dict = {
        "image_width": img_w,
        "image_height": img_h,
        "source_dpi": SPEC_DPI,
        "page_width": img_w // 2 if paper_size == "A4" else img_w,
        "anchors": _generate_anchors(img_w, img_h),
        "objective_groups": [],
        "columns": [],
    }

    objectives, fillins, essays = _classify_questions(questions)

    # 第 1 栏 x 范围
    col_margin = _mm_to_px_200(COL_MARGIN_MM)
    col_w = img_w // columns
    col1_x1 = _mm_to_px_200(ANCHOR_MARGIN_MM + ANCHOR_W_MM) + col_margin
    col1_x2 = col_w - col_margin

    # Header 区域底部
    header_bottom = _mm_to_px_200(ANCHOR_MARGIN_MM + ANCHOR_H_MM + HEADER_HEIGHT_MM)

    # 考号信息
    if exam_number_digits > 0:
        skeleton["exam_number_digits"] = exam_number_digits

    # "第 I 卷 选择题" 分节标题
    section1_y = header_bottom
    if objectives:
        section1_y += _mm_to_px_200(SECTION_HEADER_MM)

    # 选择题组
    obj_groups, obj_bottom = _build_objective_groups(
        objectives, col1_x1, col1_x2, section1_y,
    )
    skeleton["objective_groups"] = obj_groups

    # "第 II 卷 非选择题" 分节标题
    section2_y = obj_bottom
    if fillins or essays:
        section2_y += _mm_to_px_200(SECTION_HEADER_MM)

    # 填空题组（紧凑排列在第1栏，选择题下方）
    fillin_group, fillin_bottom = _build_fillin_group(
        fillins, col1_x1, col1_x2, section2_y,
    )
    if fillin_group:
        skeleton["fillin_group"] = fillin_group

    # "三、解答题" 标题预留
    essay_start = fillin_bottom
    if essays:
        essay_start += _mm_to_px_200(SECTION_HEADER_MM)
    skeleton["essay_start_y"] = essay_start

    # 记录分节位置供 renderer 使用
    skeleton["section_headers"] = {
        "section1_y": header_bottom,      # "第 I 卷 选择题"
        "section2_y": obj_bottom,          # "第 II 卷 非选择题"
        "fillin_title_y": section2_y,      # "二、填空题..."
        "essay_title_y": fillin_bottom,    # "三、解答题..."
    }
    skeleton["has_objectives"] = bool(objectives)
    skeleton["has_fillins"] = bool(fillins)
    skeleton["has_essays"] = bool(essays)
    skeleton["fillin_count"] = len(fillins)
    skeleton["essay_count"] = len(essays)
    skeleton["essay_total_score"] = sum(q.get("score", 0) for q in essays)

    # 栏定义 — 解答题可用区域（正面 + 背面）
    anchor_bottom = _mm_to_px_200(ANCHOR_MARGIN_MM + ANCHOR_H_MM)
    page_bottom = img_h - _mm_to_px_200(ANCHOR_MARGIN_MM + ANCHOR_H_MM)

    cols = []
    # ── 正面（page 0）──
    for ci in range(columns):
        cx1 = ci * col_w + col_margin
        cx2 = (ci + 1) * col_w - col_margin

        if ci == 0:
            # 第 1 栏：从解答题起始位置开始（选择题+填空题之后）
            cy1 = essay_start
        else:
            # 其他栏：从锚点底部开始
            cy1 = anchor_bottom + _mm_to_px_200(2.0)

        cols.append({
            "id": f"col_{ci + 1}",
            "x1": cx1,
            "x2": cx2,
            "y1": cy1,
            "y2": page_bottom,
            "page": 0,
        })

    # ── 背面（page 1）── A3 双面印刷
    for ci in range(columns):
        cx1 = ci * col_w + col_margin
        cx2 = (ci + 1) * col_w - col_margin
        cy1 = anchor_bottom + _mm_to_px_200(2.0)  # 背面全部从锚点底部开始

        cols.append({
            "id": f"col_{ci + 1}_back",
            "x1": cx1,
            "x2": cx2,
            "y1": cy1,
            "y2": page_bottom,
            "page": 1,
        })

    skeleton["columns"] = cols

    skeleton["_needs_finalize"] = True

    return skeleton
