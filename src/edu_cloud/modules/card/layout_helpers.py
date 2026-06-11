"""Pure layout helpers extracted from ai/tools/card_layout.py.

No dependency on ToolContext, registry, or any old engine module.
Used by card/router.py and engine/tools/card_layout.py.
"""
from __future__ import annotations

import copy
import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

_EDITOR_LAYOUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "editor_layouts"


def is_biology_generic_pollution(layout: dict, config: dict, subject_name: str) -> bool:
    """生物 generic 污染指纹（2026-06 事故）。

    前端 createDefaultLayout 兜底布局（A4 单栏、11选择/3填空）曾被误存为生物
    saved layout。命中指纹的数据不得进入也不得离开持久层：
    GET / _load_layout（auto-layout、parse-answers、AI card_layout 共用）
    fail-closed 回退学科默认，PUT 拒绝写入。指纹五维：
    subjectTitle/科目=生物、paper=A4、双面各 1 列、choiceCount=11、fillCount=3。
    """
    if config.get("subjectTitle") != "生物" and subject_name != "生物":
        return False
    if (layout.get("paper") or config.get("paperSize")) != "A4":
        return False
    sides = layout.get("sides") or []
    if not isinstance(sides, list):
        return False
    cols = [len(s.get("columns") or []) for s in sides if isinstance(s, dict)]
    if cols != [1, 1]:
        return False
    return config.get("choiceCount") == 11 and config.get("fillCount") == 3

# ── 排版常量 ──

BLANK_SHORT = "30%"
BLANK_MEDIUM = "48%"
BLANK_LONG = "100%"

COL_TOTAL_H = 270
LINE_H = 8
HEADER_H = 10
SUB_LABEL_H = 5
SUB_GAP = 3
ESSAY_PADDING = 5
SAFETY_MARGIN = 0.9

VISUAL_LINE_H = 10
VISUAL_LINE_MAX = 15
VISUAL_Q_GAP = 5
SCORE_BONUS_PER_PT = 0.5

FIXED_TITLE_H = 8
FIXED_INFO_H = 31
FIXED_NOTICE_H = 20
FIXED_SECTION_BAR_H = 6
FIXED_BASE_H = FIXED_TITLE_H + FIXED_INFO_H + FIXED_NOTICE_H + FIXED_SECTION_BAR_H * 2
CHOICE_ROW_H = 5

CHARS_PER_LINE = {"30%": 8, "48%": 14, "100%": 30}


def _pick_blank_width(text: str | None) -> str:
    if not text:
        return BLANK_LONG
    length = len(text.strip())
    if length <= 8:
        return BLANK_SHORT
    if length <= 20:
        return BLANK_MEDIUM
    return BLANK_LONG


def _make_blanks_for_answer(text: str | None) -> list[dict]:
    if not text or not text.strip():
        return [{"w": BLANK_LONG, "answer": ""}]
    ans = text.strip()
    w = _pick_blank_width(ans)
    cpl = CHARS_PER_LINE[w]
    WIDER = {"30%": "48%", "48%": "100%", "100%": "100%"}
    cont_w = WIDER[w]
    cont_cpl = CHARS_PER_LINE[cont_w]

    if len(ans) <= cpl:
        return [{"w": w, "answer": ans}]

    blanks = [{"w": w, "answer": ans[:cpl]}]
    remaining = ans[cpl:]

    while remaining:
        if len(remaining) <= cont_cpl:
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
    blanks = sub.get("blanks", [])
    if not blanks:
        return 1
    groups = []
    for b in blanks:
        if not b.get("continuation") or not groups:
            groups.append([b])
        else:
            groups[-1].append(b)
    rows = 0
    i = 0
    while i < len(groups):
        g = groups[i]
        is_short = len(g) == 1 and g[0].get("w") == "30%"
        if is_short and i + 1 < len(groups):
            g2 = groups[i + 1]
            is_short2 = len(g2) == 1 and g2[0].get("w") == "30%"
            if is_short2:
                rows += 1
                i += 2
                continue
        rows += len(g)
        i += 1
    return max(rows, 1)


def _estimate_question_height(q_result: dict) -> float:
    h = HEADER_H + ESSAY_PADDING
    for sub in q_result["subs"]:
        h += SUB_LABEL_H
        h += _count_visual_rows(sub) * LINE_H
        h += SUB_GAP
    return h


def _estimate_fixed_height(config: dict) -> float:
    choice_count = config.get("choiceCount", 0)
    options = config.get("optionCount", 4)
    per_row = config.get("choicePerRow", 20)
    choice_rows = math.ceil(choice_count / per_row) * (options + 1) if choice_count > 0 else 0
    return FIXED_BASE_H + choice_rows * CHOICE_ROW_H


def _extract_anchors(layout: dict) -> dict[int, tuple[str, int]]:
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
    if not parsed_questions:
        return {"questions": [], "columns": [], "total_estimated_lines": 0}

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

    fixed_h = _estimate_fixed_height(config or {})
    col0_avail = (COL_TOTAL_H - fixed_h) * SAFETY_MARGIN
    col_avail = COL_TOTAL_H * SAFETY_MARGIN

    slots = [
        {"side": "A", "col": 0, "capacity": max(0, col0_avail), "items": []},
        {"side": "A", "col": 1, "capacity": col_avail, "items": []},
        {"side": "A", "col": 2, "capacity": col_avail, "items": []},
        {"side": "B", "col": 0, "capacity": col_avail, "items": []},
        {"side": "B", "col": 1, "capacity": col_avail, "items": []},
        {"side": "B", "col": 2, "capacity": col_avail, "items": []},
    ]

    slot_idx = {}
    for i, s in enumerate(slots):
        slot_idx[(s["side"], s["col"])] = i

    anchors = _extract_anchors(existing_layout) if existing_layout else {}

    def _assign_to_slots_optimal(items: list, target_slots: list):
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
        unanchored = []
        for r in results:
            anchor = anchors.get(r["qno"])
            if anchor and anchor in slot_idx:
                slots[slot_idx[anchor]]["items"].append(r)
            else:
                unanchored.append(r)

        last_anchor_slot = max(
            (slot_idx[a] for a in anchors.values() if a in slot_idx), default=0
        )
        for r in unanchored:
            placed = False
            for s in slots[last_anchor_slot:] + slots[:last_anchor_slot]:
                used = sum(it["_height_mm"] for it in s["items"])
                if used + r["_height_mm"] <= s["capacity"]:
                    s["items"].append(r)
                    placed = True
                    break
            if not placed:
                slots[-1]["items"].append(r)

        for si in range(len(slots)):
            s = slots[si]
            while len(s["items"]) > 1:
                used = sum(it["_height_mm"] for it in s["items"])
                if used <= s["capacity"]:
                    break
                evicted = s["items"].pop()
                placed = False
                for ti in range(si + 1, len(slots)):
                    target = slots[ti]
                    t_used = sum(it["_height_mm"] for it in target["items"])
                    if t_used + evicted["_height_mm"] <= target["capacity"]:
                        target["items"].append(evicted)
                        placed = True
                        break
                if not placed:
                    s["items"].append(evicted)
                    break
    else:
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

    ROW_GAP = 2.5
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

    columns = []
    for slot in slots:
        if not slot["items"]:
            continue
        items = slot["items"]
        n_items = len(items)
        gap_total = max(0, n_items - 1) * VISUAL_Q_GAP
        ideal_total = sum(it["_ideal_mm"] for it in items) + gap_total
        col_cap = slot["capacity"] / SAFETY_MARGIN

        if ideal_total <= col_cap:
            for it in items:
                it["targetHeight_mm"] = round(it["_ideal_mm"], 1)
        else:
            usable = col_cap - gap_total
            ideal_sum = sum(it["_ideal_mm"] for it in items)
            for it in items:
                ratio = it["_ideal_mm"] / ideal_sum if ideal_sum > 0 else 1
                compressed = usable * ratio
                vrows = it.get("_visual_rows", sum(_count_visual_rows(s) for s in it["subs"]))
                minimum = HEADER_H + vrows * 8 + len(it["subs"]) * (SUB_LABEL_H + SUB_GAP)
                it["targetHeight_mm"] = round(max(compressed, minimum), 1)

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

    for r in results:
        r["estimated_height_mm"] = round(r.pop("_height_mm"), 1)
        r.pop("_ideal_mm", None)
        r.pop("_visual_rows", None)

    return {"questions": results, "columns": columns}


# ── 布局文件读写 ──

def strip_runtime_render_fields(value):
    """递归剥离下划线前缀的运行时渲染字段（_side/_col/_sideIdx 等）。

    这些 key 由前端 render.js 渲染时注入、或由 TQL/SUBJECT_CONFIGS 布局
    生成器携带，仅服务当次渲染交互，不属于持久化契约；editor_layouts
    持久层必须与 canonical 资产同等净化（pack3）。返回净化后的新结构，
    不修改入参。
    """
    if isinstance(value, dict):
        return {
            k: strip_runtime_render_fields(v)
            for k, v in value.items()
            if not (isinstance(k, str) and k.startswith("_"))
        }
    if isinstance(value, list):
        return [strip_runtime_render_fields(v) for v in value]
    return value


def _get_layout_path(school_id: str, subject_id: str) -> Path:
    _EDITOR_LAYOUT_DIR.mkdir(exist_ok=True)
    return _EDITOR_LAYOUT_DIR / f"{school_id}_{subject_id}.json"


def _load_layout(school_id: str, subject_id: str, subject_name: str) -> dict:
    """加载已保存布局；文件缺失/损坏/命中污染指纹时回退学科默认。

    已知 canonical 学科的默认资产本身不可用时，get_default_layout 抛
    CanonicalLayoutError 并由本函数原样传播（fail-closed，pack3）。
    auto-layout、parse-answers v2、AI card_layout 工具共用本入口。
    回退分支返回 deepcopy：调用方会原地修改并回写（_apply_to_regions →
    _save_layout），不得污染 subject_defaults._LAYOUT_CACHE 模块级缓存。
    """
    from edu_cloud.modules.card.rendering.subject_defaults import (
        final_canonical_layout_drift_reason,
        get_default_layout,
    )

    path = _get_layout_path(school_id, subject_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("layout"), dict):
            layout = data["layout"]
            merged_config = {**(layout.get("config") or {}), **(data.get("config") or {})}
            if is_biology_generic_pollution(layout, merged_config, subject_name):
                logger.warning(
                    "_load_layout: saved layout %s matches biology generic pollution "
                    "fingerprint (A4 [1,1] choice=11 fill=3), falling back to subject default",
                    path.name,
                )
            else:
                drift_reason = final_canonical_layout_drift_reason(layout, merged_config, subject_name)
                if drift_reason:
                    logger.warning(
                        "_load_layout: saved layout %s rejected by final canonical guard: %s",
                        path.name, drift_reason,
                    )
                else:
                    if "config" not in layout and "config" in data:
                        layout["config"] = data["config"]
                    return layout
        else:
            logger.warning(
                "_load_layout: unreadable or malformed layout file %s, falling back to subject default",
                path.name,
            )
    return copy.deepcopy(get_default_layout(subject_name))


def _apply_to_regions(layout: dict, layout_result: dict) -> dict:
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

    existing_regions = {}
    for side in layout.get("sides", []):
        for col in side.get("columns", []):
            for region in col.get("regions", []):
                if region.get("type") in ("essay", "fill") and region.get("qno"):
                    existing_regions[region["qno"]] = region

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
                    region = dict(existing_regions[qno])
                    region["subs"] = q["subs"]
                    region["heightRatio"] = q["heightRatio"]
                    region["score"] = q.get("score", region.get("score", 0))
                    if "targetHeight_mm" in q:
                        region["targetHeight_mm"] = q["targetHeight_mm"]
                else:
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
    data = strip_runtime_render_fields(
        {"layout": layout, "config": layout.get("config", {}), "choices": []}
    )
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    logger.info("card_layout saved: %s", path.name)
