"""小微答题卡智能排版工具。

三个工具：
1. card_parse_answers  — 解析答案 .docx → 结构化数据
2. card_auto_layout    — 结构化答案 → 空间分配 → 保存到编辑器
3. card_adjust_layout  — 语义调整（"第17题加大" / "18题第2空改短"）
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)

_EDITOR_LAYOUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "editor_layouts"

# ── 排版常量 ──

# 每个空的宽度选项（与前端 panel.js sizeToBlankWidth 一致）
BLANK_SHORT = "30%"    # 短答案（≤8 字符）
BLANK_MEDIUM = "48%"   # 中等答案（≤20 字符）
BLANK_LONG = "100%"    # 长答案（>20 字符）

# 物理尺寸（mm），与前端 CSS 对齐
COL_TOTAL_H = 270       # 列可用高度（297 减上下 warning/margin）
LINE_H = 8              # 每行答题线高度（含行距）——用于装箱估算
HEADER_H = 10           # 题号行高度（"17.（本小题满分 12 分）"）
SUB_LABEL_H = 5         # 小问标签高度（"（1）"）
SUB_GAP = 3             # 小问间距
ESSAY_PADDING = 5       # essay-item 上下 padding (2mm+3mm)
SAFETY_MARGIN = 0.9     # 安全系数，防止微小溢出

# 视觉排版常量
VISUAL_LINE_H = 10      # 每条横线的理想书写高度（mm）
VISUAL_LINE_MAX = 15    # 每条横线的最大高度（防止独占列时过度拉伸）
VISUAL_Q_GAP = 5        # 题与题之间的分隔间距（mm）
SCORE_BONUS_PER_PT = 0.5  # 每分额外空间（mm），高分题略多空间

# col0 fixed 区域高度估算（mm）
FIXED_TITLE_H = 8       # 标题区
FIXED_INFO_H = 31       # 信息区（18*1.5 + padding）
FIXED_NOTICE_H = 20     # 注意事项
FIXED_SECTION_BAR_H = 6 # "选择题" / "非选择题" 横幅
FIXED_BASE_H = FIXED_TITLE_H + FIXED_INFO_H + FIXED_NOTICE_H + FIXED_SECTION_BAR_H * 2
CHOICE_ROW_H = 5        # 每行选择题高度（含行距）


# 每种宽度一行能容纳的字符数
CHARS_PER_LINE = {"30%": 8, "48%": 14, "100%": 30}


def _pick_blank_width(text: str | None) -> str:
    """根据答案长度选择空宽度。"""
    if not text:
        return BLANK_LONG
    length = len(text.strip())
    if length <= 8:
        return BLANK_SHORT
    if length <= 20:
        return BLANK_MEDIUM
    return BLANK_LONG


def _make_blanks_for_answer(text: str | None) -> list[dict]:
    """为一个答案生成 blank 列表。答案超出一行容量时自动加续行。

    续行宽度升级：首行按答案长度选宽度，续行升一档（无小问标签占位，可用空间更大）。
    孤字合并：末行≤3字符时合并到上一行，避免只有一个括号或几个字独占一行。
    """
    if not text or not text.strip():
        return [{"w": BLANK_LONG, "answer": ""}]
    ans = text.strip()
    w = _pick_blank_width(ans)
    cpl = CHARS_PER_LINE[w]
    # 续行升一档宽度（30%→48%，48%→100%，100%不变）
    WIDER = {"30%": "48%", "48%": "100%", "100%": "100%"}
    cont_w = WIDER[w]
    cont_cpl = CHARS_PER_LINE[cont_w]

    if len(ans) <= cpl:
        return [{"w": w, "answer": ans}]

    # 首行
    blanks = [{"w": w, "answer": ans[:cpl]}]
    remaining = ans[cpl:]

    while remaining:
        if len(remaining) <= cont_cpl:
            # 最后一段：检查孤字合并（≤3字符合并到上一行）
            if len(remaining) <= 3 and blanks:
                blanks[-1]["answer"] += remaining
            else:
                blanks.append({"w": cont_w, "answer": remaining, "continuation": True})
            break
        chunk = remaining[:cont_cpl]
        blanks.append({"w": cont_w, "answer": chunk, "continuation": True})
        remaining = remaining[cont_cpl:]

    return blanks


def _count_visual_rows(sub: dict) -> int:
    """计算一个小问的视觉行数（短空配对同行，续行不独立计数）。"""
    blanks = sub.get("blanks", [])
    if not blanks:
        return 1
    # 分组：非 continuation 的 blank 开始一组，continuation 追加到同组
    groups = []
    for b in blanks:
        if not b.get("continuation") or not groups:
            groups.append([b])
        else:
            groups[-1].append(b)
    # 计算视觉行：30% 短空（单行组）可两两配对
    rows = 0
    i = 0
    while i < len(groups):
        g = groups[i]
        is_short = len(g) == 1 and g[0].get("w") == "30%"
        if is_short and i + 1 < len(groups):
            g2 = groups[i + 1]
            is_short2 = len(g2) == 1 and g2[0].get("w") == "30%"
            if is_short2:
                rows += 1  # 两个短空同行
                i += 2
                continue
        rows += len(g)  # 首行 + continuation 行数
        i += 1
    return max(rows, 1)


def _estimate_question_height(q_result: dict) -> float:
    """估算一道题在页面上的物理高度（mm）——用于装箱。"""
    h = HEADER_H + ESSAY_PADDING
    for sub in q_result["subs"]:
        h += SUB_LABEL_H
        h += _count_visual_rows(sub) * LINE_H
        h += SUB_GAP
    return h


def _estimate_fixed_height(config: dict) -> float:
    """估算 col0 中 fixed 区域的总高度（mm）。"""
    choice_count = config.get("choiceCount", 0)
    options = config.get("optionCount", 4)
    # 选择题行数 = ceil(题数/每行) × (选项行数+1)
    per_row = config.get("choicePerRow", 20)
    choice_rows = math.ceil(choice_count / per_row) * (options + 1) if choice_count > 0 else 0
    return FIXED_BASE_H + choice_rows * CHOICE_ROW_H


def _extract_anchors(layout: dict) -> dict[int, tuple[str, int]]:
    """从已有 layout 提取 qno → (side, col) 锚点映射。"""
    anchors = {}
    for side in layout.get("sides", []):
        side_name = side.get("side", "A")
        for col in side.get("columns", []):
            col_idx = col.get("col", 0)
            for region in col.get("regions", []):
                if region.get("type") in ("essay", "fill") and region.get("qno"):
                    anchors[region["qno"]] = (side_name, col_idx)
    return anchors


def calculate_layout(
    parsed_questions: list[dict],
    config: dict | None = None,
    existing_layout: dict | None = None,
) -> dict:
    """核心排版算法：计算空间分配 + 列分配。

    如果提供 existing_layout，按模板锚点约束分配（保持原位）；
    无锚点时走全局最优分割装箱。

    Args:
        parsed_questions: [{qno, total_score, subs: [{sub, answers: [str]}]}, ...]
        config: layout config（用于计算 col0 fixed 高度）
        existing_layout: 已有 layout（用于提取 qno→列 锚点）
    """
    if not parsed_questions:
        return {"questions": [], "columns": [], "total_estimated_lines": 0}

    # ── Step 1: 计算每题的 subs/blanks 和物理高度 ──
    results = []
    for q in parsed_questions:
        subs = []
        for sd in q.get("subs", []):
            answers = sd.get("answers", [])
            blanks = []
            for ans in answers:
                blanks.extend(_make_blanks_for_answer(ans))
            if not blanks:
                blanks = [{"w": BLANK_LONG}]
            sub_entry = {"sub": sd["sub"], "blanks": blanks}
            if sd.get("label"):
                sub_entry["label"] = sd["label"]
            subs.append(sub_entry)
        if not subs:
            subs = [{"sub": 1, "blanks": [{"w": BLANK_LONG}] * 3}]
        results.append({
            "qno": q["qno"], "score": q.get("total_score", 0), "subs": subs,
        })

    for r in results:
        r["_height_mm"] = _estimate_question_height(r)

    # ── Step 2: 计算可用列和容量 ──
    fixed_h = _estimate_fixed_height(config or {})
    col0_avail = (COL_TOTAL_H - fixed_h) * SAFETY_MARGIN
    col_avail = COL_TOTAL_H * SAFETY_MARGIN  # col1, col2

    # 可用槽位：col0 剩余 → col1 → col2 → B面 col0 → B面 col1 → B面 col2
    slots = [
        {"side": "A", "col": 0, "capacity": max(0, col0_avail), "items": []},
        {"side": "A", "col": 1, "capacity": col_avail, "items": []},
        {"side": "A", "col": 2, "capacity": col_avail, "items": []},
        {"side": "B", "col": 0, "capacity": col_avail, "items": []},
        {"side": "B", "col": 1, "capacity": col_avail, "items": []},
        {"side": "B", "col": 2, "capacity": col_avail, "items": []},
    ]

    # ── Step 3: 装箱 ──
    # 策略 A（有模板锚点）：按锚点分配到原列，新题和溢出才重分配
    # 策略 B（无锚点）：全局最优分割装箱

    slot_idx = {}  # (side, col) → slot index
    for i, s in enumerate(slots):
        slot_idx[(s["side"], s["col"])] = i

    anchors = _extract_anchors(existing_layout) if existing_layout else {}

    def _assign_to_slots_optimal(items: list, target_slots: list):
        """将有序题目列表分配到 3 个 slot 中（最优分割）。"""
        if len(target_slots) == 1 or not items:
            target_slots[0]["items"].extend(items)
            return
        if len(target_slots) == 2:
            heights = [it["_height_mm"] for it in items]
            total = sum(heights)
            best_k, best_max = 0, total
            left_h = 0
            for k in range(len(items) + 1):
                right_h = total - left_h
                if max(left_h, right_h) < best_max:
                    best_max = max(left_h, right_h)
                    best_k = k
                if k < len(items):
                    left_h += heights[k]
            target_slots[0]["items"].extend(items[:best_k])
            target_slots[1]["items"].extend(items[best_k:])
            return
        heights = [it["_height_mm"] for it in items]
        n = len(items)
        caps = [s["capacity"] for s in target_slots]
        prefix = [0.0] * (n + 1)
        for i in range(n):
            prefix[i + 1] = prefix[i] + heights[i]
        best_k1, best_k2, best_cost = 0, 0, float("inf")
        for k1 in range(n + 1):
            h0 = prefix[k1]
            for k2 in range(k1, n + 1):
                h1 = prefix[k2] - prefix[k1]
                h2 = prefix[n] - prefix[k2]
                cost = 0
                for h, cap in zip([h0, h1, h2], caps):
                    pen = h + (h - cap) * 2 if h > cap else h
                    cost = max(cost, pen)
                if cost < best_cost:
                    best_cost = cost
                    best_k1 = k1
                    best_k2 = k2
        target_slots[0]["items"].extend(items[:best_k1])
        target_slots[1]["items"].extend(items[best_k1:best_k2])
        target_slots[2]["items"].extend(items[best_k2:])

    if anchors:
        # 策略 A：模板约束装箱
        unanchored = []
        for r in results:
            anchor = anchors.get(r["qno"])
            if anchor and anchor in slot_idx:
                slots[slot_idx[anchor]]["items"].append(r)
            else:
                unanchored.append(r)

        # 新增题目：按 qno 顺序插入到有剩余空间的列（优先 A 面）
        for r in unanchored:
            placed = False
            for s in slots:
                used = sum(it["_height_mm"] for it in s["items"])
                if used + r["_height_mm"] <= s["capacity"]:
                    s["items"].append(r)
                    placed = True
                    break
            if not placed:
                # 所有列都满：放到 B 面最后一列
                slots[-1]["items"].append(r)

        # 溢出处理：列超载时把末尾题目移到有空间的列
        for si, s in enumerate(slots):
            while len(s["items"]) > 1:
                used = sum(it["_height_mm"] for it in s["items"])
                if used <= s["capacity"]:
                    break
                evicted = s["items"].pop()
                placed = False
                for target in slots[si + 1:]:
                    t_used = sum(it["_height_mm"] for it in target["items"])
                    if t_used + evicted["_height_mm"] <= target["capacity"]:
                        target["items"].append(evicted)
                        placed = True
                        break
                if not placed:
                    slots[-1]["items"].append(evicted)
                    break
    else:
        # 策略 B：全局最优分割装箱（无模板时）
        total_h = sum(r["_height_mm"] for r in results)
        a_total_cap = slots[0]["capacity"] + slots[1]["capacity"] + slots[2]["capacity"]

        if total_h <= a_total_cap:
            _assign_to_slots_optimal(results, [slots[0], slots[1], slots[2]])
        else:
            _assign_to_slots_optimal(results, [slots[0], slots[1], slots[2]])
            overflow = []
            for s in slots[0:3]:
                col_overflow = []
                while s["items"]:
                    used = sum(it["_height_mm"] for it in s["items"])
                    if used <= s["capacity"] or len(s["items"]) <= 1:
                        break
                    col_overflow.append(s["items"].pop())
                col_overflow.reverse()
                overflow.extend(col_overflow)
            if overflow:
                _assign_to_slots_optimal(overflow, [slots[3], slots[4], slots[5]])

    # ── Step 4: 视觉理想高度计算 ──
    # 用视觉行数（短空配对、续行合并），不用 blank 原始计数
    ROW_GAP = 2.5  # 与 CSS --essay-row-gap 对齐
    for r in results:
        total_rows = sum(_count_visual_rows(s) for s in r["subs"])
        sub_count = len(r["subs"])
        ideal = (HEADER_H + ESSAY_PADDING
                 + total_rows * VISUAL_LINE_H
                 + max(0, total_rows - 1) * ROW_GAP
                 + sub_count * (SUB_LABEL_H + SUB_GAP)
                 + r.get("score", 0) * SCORE_BONUS_PER_PT)
        r["_ideal_mm"] = ideal
        r["_visual_rows"] = total_rows

    # ── Step 5: per-column 弹性分配 ──
    # 如果列内理想总高 ≤ 列容量：按理想高度定额（底部留白）
    # 如果理想总高 > 列容量：按比例压缩，但保证最小行高
    columns = []
    for slot in slots:
        if not slot["items"]:
            continue
        items = slot["items"]
        n_items = len(items)
        gap_total = max(0, n_items - 1) * VISUAL_Q_GAP
        ideal_total = sum(it["_ideal_mm"] for it in items) + gap_total
        col_cap = slot["capacity"] / SAFETY_MARGIN  # 用物理列高，不用安全容量

        if ideal_total <= col_cap:
            # 列有富余：按理想高度定额
            for it in items:
                it["targetHeight_mm"] = round(it["_ideal_mm"], 1)
        else:
            # 列超载：按比例压缩（保底 = 每空最小行高 7.5mm）
            usable = col_cap - gap_total
            ideal_sum = sum(it["_ideal_mm"] for it in items)
            for it in items:
                ratio = it["_ideal_mm"] / ideal_sum if ideal_sum > 0 else 1
                compressed = usable * ratio
                # 保底：题头 + 每视觉行最小 8mm
                vrows = it.get("_visual_rows", sum(_count_visual_rows(s) for s in it["subs"]))
                minimum = HEADER_H + vrows * 8 + len(it["subs"]) * (SUB_LABEL_H + SUB_GAP)
                it["targetHeight_mm"] = round(max(compressed, minimum), 1)

        # 同时保留 heightRatio（兼容旧渲染路径）
        col_total = sum(it["_height_mm"] for it in items)
        for it in items:
            it["heightRatio"] = round(it["_height_mm"] / col_total, 4) if col_total > 0 else 1

        columns.append({
            "side": slot["side"], "col": slot["col"],
            "questions": [it["qno"] for it in items],
            "used_mm": round(sum(it["_height_mm"] for it in items), 1),
            "capacity_mm": round(slot["capacity"], 1),
            "qGap_mm": VISUAL_Q_GAP if n_items > 1 else 0,
        })

    # 清理内部字段
    for r in results:
        r["estimated_height_mm"] = round(r.pop("_height_mm"), 1)
        r.pop("_ideal_mm", None)
        r.pop("_visual_rows", None)

    return {"questions": results, "columns": columns}


# ── 布局文件读写 ──

def _get_layout_path(school_id: str, subject_id: str) -> Path:
    _EDITOR_LAYOUT_DIR.mkdir(exist_ok=True)
    return _EDITOR_LAYOUT_DIR / f"{school_id}_{subject_id}.json"


def _load_layout(school_id: str, subject_id: str, subject_name: str) -> dict:
    path = _get_layout_path(school_id, subject_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            layout = data.get("layout", {})
            if "config" not in layout and "config" in data:
                layout["config"] = data["config"]
            return layout
        except (json.JSONDecodeError, OSError):
            pass
    from edu_cloud.modules.card.rendering.subject_defaults import get_default_layout
    return get_default_layout(subject_name)


def _apply_to_regions(layout: dict, layout_result: dict) -> dict:
    """非破坏式 merge：按 qno 更新排版数据，保留用户手调字段。

    策略：
    1. 已有 region 且 qno 匹配 → 更新 subs/blanks/heightRatio/score，保留 cuts/texts/images 等
    2. 新增题目（模板中没有的 qno）→ 插入到有剩余空间的列
    3. 删除题目（模板有但答案没有的 qno）→ 保留 region（用户手动删除）
    """
    qmap = {q["qno"]: q for q in layout_result["questions"]}
    col_assign = {}
    for col_info in layout_result.get("columns", []):
        key = (col_info["side"], col_info["col"])
        col_assign[key] = col_info["questions"]

    if not col_assign:
        for side in layout.get("sides", []):
            for col in side.get("columns", []):
                for region in col.get("regions", []):
                    if region.get("type") == "essay" and region.get("qno") in qmap:
                        lq = qmap[region["qno"]]
                        region["heightRatio"] = lq["heightRatio"]
                        region["subs"] = lq["subs"]
                        region["score"] = lq.get("score", region.get("score", 0))
        return layout

    # 建立已有 region 索引：qno → region dict（保留引用）
    existing_regions = {}
    for side in layout.get("sides", []):
        for col in side.get("columns", []):
            for region in col.get("regions", []):
                if region.get("type") in ("essay", "fill") and region.get("qno"):
                    existing_regions[region["qno"]] = region

    # 收集已分配的 qno 集合，用于检测新增题目
    assigned_qnos = set()
    for qnos in col_assign.values():
        assigned_qnos.update(qnos)

    for side in layout.get("sides", []):
        side_name = side.get("side", "A")
        orig_cols = {c["col"]: c for c in side.get("columns", [])}

        side_col_nums = sorted(set(
            col for (s, col) in col_assign if s == side_name
        ))
        max_col = max(side_col_nums) if side_col_nums else (max(orig_cols.keys()) if orig_cols else 2)

        new_columns = []
        for ci in range(max_col + 1):
            orig = orig_cols.get(ci, {"col": ci, "regions": []})
            fixed_regions = [r for r in orig.get("regions", []) if r.get("type") == "fixed"]

            qnos = col_assign.get((side_name, ci), [])
            essay_regions = []
            for qno in qnos:
                if qno not in qmap:
                    continue
                q = qmap[qno]

                if qno in existing_regions:
                    # merge：更新排版数据，保留用户手调字段
                    region = dict(existing_regions[qno])
                    region["subs"] = q["subs"]
                    region["heightRatio"] = q["heightRatio"]
                    region["score"] = q.get("score", region.get("score", 0))
                    if "targetHeight_mm" in q:
                        region["targetHeight_mm"] = q["targetHeight_mm"]
                else:
                    # 新增题目
                    region = {
                        "id": f"essay-Q{qno}",
                        "type": "essay",
                        "qno": qno,
                        "score": q.get("score", 0),
                        "subs": q["subs"],
                        "heightRatio": q["heightRatio"],
                    }
                    if "targetHeight_mm" in q:
                        region["targetHeight_mm"] = q["targetHeight_mm"]

                essay_regions.append(region)

            # 保留不在本次答案中的手工 region（用户手动添加的题目）
            for r in orig.get("regions", []):
                if r.get("type") in ("essay", "fill") and r.get("qno"):
                    if r["qno"] not in assigned_qnos:
                        essay_regions.append(r)

            col_data = {"col": ci, "regions": fixed_regions + essay_regions}
            ci_info = next((c for c in layout_result.get("columns", [])
                           if c["side"] == side_name and c["col"] == ci), None)
            if ci_info and ci_info.get("qGap_mm"):
                col_data["qGap_mm"] = ci_info["qGap_mm"]
            new_columns.append(col_data)

        side["columns"] = new_columns

    return layout


def _save_layout(school_id: str, subject_id: str, layout: dict):
    path = _get_layout_path(school_id, subject_id)
    data = {"layout": layout, "config": layout.get("config", {}), "choices": []}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    logger.info("card_layout saved: %s", path.name)


# ══════════════════════════════════════════════════════════════
# 工具 1：解析答案文件
# ══════════════════════════════════════════════════════════════

@tools.register(
    name="card_parse_answers",
    description="解析答案文档（.docx），提取每道主观题的小问和标准答案文本，返回结构化数据供排版使用。",
    category="L4_action", module_code="card", domain="exam",
    allowed_roles=["platform_admin", "principal", "academic_director", "subject_teacher"],
    risk_level="low", is_read_only=True, sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "答案文件路径（.docx）"},
        },
        "required": ["file_path"],
    },
)
async def card_parse_answers(input: dict, ctx: ToolContext) -> ToolResult:
    file_path = input["file_path"]
    if not Path(file_path).exists():
        return ToolResult(success=False, error=f"文件不存在: {file_path}")
    try:
        from edu_cloud.modules.card.parser.answer_parser import parse_answer_docx
        questions = parse_answer_docx(file_path)
        if not questions:
            return ToolResult(success=False, error="未解析到主观题")
        summary = []
        for q in questions:
            bc = sum(len(s["answers"]) for s in q["subs"])
            summary.append(f'Q{q["qno"]}({q["total_score"]}分/{len(q["subs"])}问/{bc}空)')
        return ToolResult(success=True, data={
            "questions": questions, "summary": "、".join(summary), "count": len(questions),
        })
    except Exception as e:
        return ToolResult(success=False, error=f"解析失败: {e}")


# ══════════════════════════════════════════════════════════════
# 工具 2：自动排版（从解析后的答案数据）
# ══════════════════════════════════════════════════════════════

@tools.register(
    name="card_auto_layout",
    description="根据解析后的答案数据自动计算答题卡排版（每题空间+每空宽度），并保存到编辑器。先用 card_parse_answers 获取 questions 数据。",
    category="L4_action", module_code="card", domain="exam",
    allowed_roles=["platform_admin", "principal", "academic_director", "subject_teacher"],
    risk_level="low", is_read_only=False, sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "subject_id": {"type": "string", "description": "科目 ID"},
            "parsed_questions": {
                "type": "array", "description": "card_parse_answers 返回的 questions 数组",
                "items": {"type": "object"},
            },
        },
        "required": ["subject_id", "parsed_questions"],
    },
)
async def card_auto_layout(input: dict, ctx: ToolContext) -> ToolResult:
    from edu_cloud.modules.exam.models import Subject

    subject_id = input["subject_id"]
    parsed_questions = input["parsed_questions"]

    subject = (await ctx.db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == ctx.school_id)
    )).scalar_one_or_none()
    if not subject:
        return ToolResult(success=False, error="科目不存在")

    layout = _load_layout(ctx.school_id, subject_id, subject.name)
    layout_result = calculate_layout(parsed_questions, layout.get("config"), existing_layout=layout)
    layout = _apply_to_regions(layout, layout_result)
    _save_layout(ctx.school_id, subject_id, layout)

    col_summary = ", ".join(
        f'{c["side"]}面col{c["col"]}=[Q{"→Q".join(str(q) for q in c["questions"])}] ({c["used_mm"]}/{c["capacity_mm"]}mm)'
        for c in layout_result.get("columns", [])
    )

    return ToolResult(success=True, data={
        "subject": subject.name,
        "layout": layout_result,
        "message": f"已为 {subject.name} 完成 {len(parsed_questions)} 题排版并保存。列分配: {col_summary}",
    })


# ══════════════════════════════════════════════════════════════
# 工具 3：语义调整
# ══════════════════════════════════════════════════════════════

@tools.register(
    name="card_adjust_layout",
    description="调整答题卡排版：修改指定题目的空间或空宽度。支持自然语言如'第17题加大'、'18题第2空改短'、'17和18匀一下'。",
    category="L4_action", module_code="card", domain="exam",
    allowed_roles=["platform_admin", "principal", "academic_director", "subject_teacher"],
    risk_level="low", is_read_only=False, sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "subject_id": {"type": "string", "description": "科目 ID"},
            "adjustments": {
                "type": "array", "description": "调整指令列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["resize", "set_blank_width", "balance"]},
                        "qno": {"type": "integer"}, "qno2": {"type": "integer"},
                        "delta": {"type": "number", "description": "resize 增减量（0.05=5%）"},
                        "sub": {"type": "integer", "description": "小问号（从1）"},
                        "blank_index": {"type": "integer", "description": "空索引（从0）"},
                        "width": {"type": "string", "enum": ["short", "medium", "long"]},
                    },
                    "required": ["action"],
                },
            },
        },
        "required": ["subject_id", "adjustments"],
    },
)
async def card_adjust_layout(input: dict, ctx: ToolContext) -> ToolResult:
    from edu_cloud.modules.exam.models import Subject

    subject_id = input["subject_id"]
    subject = (await ctx.db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == ctx.school_id)
    )).scalar_one_or_none()
    if not subject:
        return ToolResult(success=False, error="科目不存在")

    layout = _load_layout(ctx.school_id, subject_id, subject.name)

    regions = {}
    for side in layout.get("sides", []):
        for col in side.get("columns", []):
            for r in col.get("regions", []):
                if r.get("type") == "essay" and r.get("qno"):
                    regions[r["qno"]] = r

    width_map = {"short": BLANK_SHORT, "medium": BLANK_MEDIUM, "long": BLANK_LONG}
    changes = []

    for adj in input["adjustments"]:
        action = adj["action"]
        if action == "resize":
            qno = adj.get("qno")
            delta = adj.get("delta", 0.05)
            if qno in regions:
                old = regions[qno]["heightRatio"]
                regions[qno]["heightRatio"] = round(max(0.05, old + delta), 4)
                changes.append(f"Q{qno} {old:.0%}→{regions[qno]['heightRatio']:.0%}")
        elif action == "set_blank_width":
            qno, si, bi = adj.get("qno"), (adj.get("sub", 1) or 1) - 1, adj.get("blank_index", 0) or 0
            w = width_map.get(adj.get("width", "long"), BLANK_LONG)
            if qno in regions:
                subs = regions[qno].get("subs", [])
                if si < len(subs) and bi < len(subs[si].get("blanks", [])):
                    subs[si]["blanks"][bi]["w"] = w
                    changes.append(f"Q{qno}({si+1})空{bi+1}→{adj.get('width')}")
        elif action == "balance":
            q1, q2 = adj.get("qno"), adj.get("qno2")
            if q1 in regions and q2 in regions:
                avg = (regions[q1]["heightRatio"] + regions[q2]["heightRatio"]) / 2
                regions[q1]["heightRatio"] = regions[q2]["heightRatio"] = round(avg, 4)
                changes.append(f"Q{q1}+Q{q2}均衡→{avg:.0%}")

    # 归一化
    total = sum(r["heightRatio"] for r in regions.values())
    if total > 0:
        for r in regions.values():
            r["heightRatio"] = round(r["heightRatio"] / total, 4)

    _save_layout(ctx.school_id, subject_id, layout)
    return ToolResult(success=True, data={
        "changes": changes, "message": f"已调整 {len(changes)} 项并保存",
    })
