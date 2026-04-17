"""各学科答题卡默认编辑器布局 — 从 TQL 模板代码化。

数据来源：TQL 模板 D:/试卷数据/YueXiaoEr/Scanner/Templetes/ [141984xxx] 系列。
每科的 SUBJECT_CONFIGS 定义题型结构，create_subject_layout() 生成完整布局 JSON。
用户修改 SUBJECT_CONFIGS 中的数值即可调整各科默认模板。
"""
from __future__ import annotations

# ── 公共样式参数（所有学科共享，与 defaults.py 中数学模板一致） ──

_BASE_STYLE: dict = {
    "examTitle": "",
    "titleSize": 14,
    "subtitleSize": 16,
    "titleSpacing": 1,
    "subtitleSpacing": 4,
    "titleGap": 1,
    "subtitleGap": 1.5,
    "infoHeight": 18,
    "infoPadding": 2,
    "infoRowGap": 2,
    "infoFontSize": 10,
    "infoBorderWidth": 1,
    "nameLineWidth": 35,
    "digitCount": 10,
    "digitBoxSize": 4.5,
    "digitGap": 0.8,
    "barcodeWidthPct": 40,
    "barcodeTitleSize": 12,
    "noticeHeight": 20,
    "noticeLabelWidth": 6,
    "noticeLabelSize": 10,
    "noticeFontSize": 7,
    "exampleWidth": 10,
    "noticeBorderWidth": 1,
    "absentPadding": 1,
    "paperSize": "A3",
    "zoom": 66,
}


# ══════════════════════════════════════════════════════════════
# 各学科题型结构（精确对照 TQL [141984xxx] 系列）
#
#   choiceGroups : [{start, count, options, multi?}, ...]  选择题分组（真实题号）
#   fillStart    : 填空题起始题号（0=无填空）
#   fillCount    : 填空题数
#   fillScore    : 每题分值
#   essays       : [{qno, score, sub_count?}, ...]  解答题（真实题号）
#   useSideB     : 是否使用B面
#   choicePerRow : 每行几题（默认15）
# ══════════════════════════════════════════════════════════════

SUBJECT_CONFIGS: dict[str, dict] = {

    # ── 数学：8单选+3多选 | 12-14填空(TQL合并slot) | 解答15-19 ──
    "数学": {
        "choiceGroups": [
            {"start": 1, "count": 8, "options": 4},
            {"start": 9, "count": 3, "options": 4, "multi": True},
        ],
        "essays": [
            {"qno": 12, "score": 15, "page": 0},   # TQL: "12-14题" 合并填空
            {"qno": 15, "score": 13, "page": 0},
            {"qno": 16, "score": 15, "page": 0},
            {"qno": 17, "score": 15, "page": 1},
            {"qno": 18, "score": 17, "page": 1},
            {"qno": 19, "score": 17, "page": 1},
        ],
        "useSideB": True,
    },

    # ── 语文：选择题分散(1-3,6-7,10,11-12,15) | 解答题穿插 | 作文独占B面 ──
    "语文": {
        "choiceGroups": [
            {"start": 1, "count": 3, "options": 4},
            {"start": 6, "count": 2, "options": 4},
            {"start": 10, "count": 1, "options": 7, "multi": True},
            {"start": 11, "count": 2, "options": 4},
            {"start": 15, "count": 1, "options": 4},
        ],
        "essays": [
            {"qno": 4, "score": 4, "page": 0},
            {"qno": 5, "score": 6, "page": 0},
            {"qno": 8, "score": 4, "page": 0},
            {"qno": 9, "score": 6, "page": 0},
            {"qno": 13, "score": 8, "sub_count": 2, "page": 0},
            {"qno": 14, "score": 5, "page": 0},
            {"qno": 16, "score": 6, "page": 0},
            {"qno": 17, "score": 6, "page": 0},
            {"qno": 18, "score": 2, "page": 0},
            {"qno": 19, "score": 2, "page": 0},
            {"qno": 20, "score": 6, "page": 0},
            {"qno": 21, "score": 4, "page": 0},
            {"qno": 22, "score": 4, "page": 0},
            {"qno": 23, "score": 60, "page": 1},   # 作文独占B面
        ],
        "useSideB": True,
    },

    # ── 英语：55选择(11组,含3/7选项) | 56-65语法填空(3列) | 写作2节 ──
    "英语": {
        "choiceGroups": [
            {"start": 1, "count": 5, "options": 3},
            {"start": 6, "count": 5, "options": 3},
            {"start": 11, "count": 5, "options": 3},
            {"start": 16, "count": 5, "options": 3},
            {"start": 21, "count": 5, "options": 4},
            {"start": 26, "count": 5, "options": 4},
            {"start": 31, "count": 5, "options": 4},
            {"start": 36, "count": 5, "options": 7},
            {"start": 41, "count": 5, "options": 4},
            {"start": 46, "count": 5, "options": 4},
            {"start": 51, "count": 5, "options": 4},
        ],
        "fills": {"start": 56, "count": 10, "perRow": 3},
        "essays": [
            {"qno": 66, "score": 15, "sub_count": 2, "page": 0},  # 写作第一节
            {"qno": 67, "score": 25, "page": 1},    # 写作第二节
        ],
        "useSideB": True,
    },

    # ── 物理：6单选+4多选 | 解答11-15 ──
    "物理": {
        "choiceGroups": [
            {"start": 1, "count": 6, "options": 4},
            {"start": 7, "count": 4, "options": 4, "multi": True},
        ],
        "essays": [
            {"qno": 11, "score": 6},
            {"qno": 12, "score": 10},
            {"qno": 13, "score": 10},
            {"qno": 14, "score": 14},
            {"qno": 15, "score": 16},
        ],
        "useSideB": False,
    },

    # ── 化学：14选择(6组) | 解答15-18 ──
    "化学": {
        "choiceGroups": [
            {"start": 1, "count": 1, "options": 4},
            {"start": 2, "count": 4, "options": 4},
            {"start": 6, "count": 1, "options": 4},
            {"start": 7, "count": 4, "options": 4},
            {"start": 11, "count": 1, "options": 4},
            {"start": 12, "count": 3, "options": 4},
        ],
        "essays": [
            {"qno": 15, "score": 15, "page": 0},
            {"qno": 16, "score": 14, "sub_count": 2, "page": 0},
            {"qno": 17, "score": 15, "page": 1},
            {"qno": 18, "score": 14, "page": 1},
        ],
        "useSideB": True,
    },

    # ── 生物：12单选+4多选 | 解答17-21 ──
    "生物": {
        "choiceGroups": [
            {"start": 1, "count": 5, "options": 4},
            {"start": 6, "count": 5, "options": 4},
            {"start": 11, "count": 2, "options": 4},
            {"start": 13, "count": 3, "options": 4, "multi": True},
            {"start": 16, "count": 1, "options": 4, "multi": True},
        ],
        "essays": [
            {"qno": 17, "score": 12},
            {"qno": 18, "score": 12},
            {"qno": 19, "score": 12},
            {"qno": 20, "score": 12},
            {"qno": 21, "score": 12},
        ],
        "useSideB": False,
    },

    # ── 历史：16选择(4组) | 解答17-19 ──
    "历史": {
        "choiceGroups": [
            {"start": 1, "count": 5, "options": 4},
            {"start": 6, "count": 5, "options": 4},
            {"start": 11, "count": 5, "options": 4},
            {"start": 16, "count": 1, "options": 4},
        ],
        "essays": [
            {"qno": 17, "score": 17, "sub_count": 2},
            {"qno": 18, "score": 18},
            {"qno": 19, "score": 17, "sub_count": 2},
        ],
        "useSideB": False,
    },

    # ── 政治：16选择(4组) | 解答17-21 ──
    "政治": {
        "choiceGroups": [
            {"start": 1, "count": 5, "options": 4},
            {"start": 6, "count": 5, "options": 4},
            {"start": 11, "count": 5, "options": 4},
            {"start": 16, "count": 1, "options": 4},
        ],
        "essays": [
            {"qno": 17, "score": 9},
            {"qno": 18, "score": 10},
            {"qno": 19, "score": 9},
            {"qno": 20, "score": 10},
            {"qno": 21, "score": 14, "sub_count": 2},
        ],
        "useSideB": False,
    },

    # ── 地理：16选择(4组) | 解答17-19(多小问) ──
    "地理": {
        "choiceGroups": [
            {"start": 1, "count": 5, "options": 4},
            {"start": 6, "count": 5, "options": 4},
            {"start": 11, "count": 5, "options": 4},
            {"start": 16, "count": 1, "options": 4},
        ],
        "essays": [
            {"qno": 17, "score": 16, "sub_count": 3},
            {"qno": 18, "score": 16, "sub_count": 3},
            {"qno": 19, "score": 20, "sub_count": 4},
        ],
        "useSideB": False,
    },
}


# ══════════════════════════════════════════════════════════════
# 布局生成器
# ══════════════════════════════════════════════════════════════

def _build_subs(sub_count: int, blanks_per_sub: int = 3) -> list[dict]:
    """生成小问标记列表。"""
    if not sub_count or sub_count <= 0:
        return []
    return [
        {"sub": i + 1, "blanks": [{"w": "100%"}] * blanks_per_sub}
        for i in range(sub_count)
    ]


def tql_to_editor_layout(tpl_path: str, subject_title: str = "") -> dict:
    """从 TQL 模板文件精确转换为编辑器布局 JSON。

    直接使用 TQL 的像素坐标计算 heightRatio 和栏分配，
    不做任何近似或 round-robin——精确复刻 TQL 布局。
    """
    from edu_cloud.modules.card.rendering.tpl_parser import parse_tpl_file

    sk = parse_tpl_file(tpl_path)
    columns = sk["columns"]
    obj_groups = sk["objective_groups"]
    slots = sk["subjective_slots"]
    image_width = sk["image_width"]
    image_height = sk["image_height"]
    paper_size = sk["paper_size"]
    is_a4_dual = sk.get("is_a4_dual", False)
    n_essay_cols = len(columns)

    # ── choiceGroups（含 TQL 坐标用于前端布局） ──
    choice_groups = []
    for g in obj_groups:
        r = g["rect"]
        cg: dict = {
            "start": g["start_no"],
            "count": g["count"],
            "options": g["options"],
            # TQL 归一化坐标（百分比），前端用于布局
            "x": round(r["x1"] / image_width * 100, 1) if image_width else 0,
            "y": round(r["y1"] / image_height * 100, 1) if image_height else 0,
            "w": round((r["x2"] - r["x1"]) / image_width * 100, 1) if image_width else 0,
        }
        if g["multi_select"]:
            cg["multi"] = True
        choice_groups.append(cg)
    total_choices = sum(g["count"] for g in choice_groups)
    max_options = max((g["options"] for g in choice_groups), default=4)

    # ── 按 x 中点分配 slot 到最近的 column ──
    # A4 双面：只有 1 栏，page0 → A 面，page1 → B 面
    col_slots_a: dict[str, list] = {c["id"]: [] for c in columns}  # page 0
    col_slots_b: dict[str, list] = {c["id"]: [] for c in columns}  # page 1
    seen_slots_a: dict[str, dict] = {}  # page 0 已见 slot
    seen_slots_b: dict[str, dict] = {}  # page 1 已见 slot（A4 双面用）

    for s in slots:
        r = s["rect"]
        page = s["inpage"]

        # A4 双面时只有 1 栏，直接用；A3 时按 x 中点匹配最近栏
        if is_a4_dual:
            best_col = columns[0]
        else:
            cx = (r["x1"] + r["x2"]) / 2
            best_col = min(columns, key=lambda c: abs((c["x1"] + c["x2"]) / 2 - cx))

        h = r["y2"] - r["y1"]
        col_h = best_col["y2"] - best_col["y1"]
        hr = h / col_h if col_h > 0 else 1.0

        slot_key = s["slot_id"]

        if is_a4_dual:
            # A4 双面：每面独立管理 region
            # 跨面题（同 slot_key 出现在两面）→ A 面保留完整 score，B 面标记为续写
            seen = seen_slots_a if page == 0 else seen_slots_b
            if slot_key in seen:
                # 同面内的同题号子问：合并
                existing = seen[slot_key]
                existing["score"] += s["score"]
                existing["sub_count"] = existing.get("sub_count", 1) + 1
                existing["heightRatio"] = max(existing["heightRatio"], hr)
                continue

            # 判断是否是跨面续写（A 面已有同题号）
            is_continuation = (page == 1 and slot_key in seen_slots_a)
            entry = {
                "slot_id": slot_key,
                "score": s["score"] if not is_continuation else 0,  # 续写不重复计分
                "heightRatio": round(hr, 4),
                "page": page,
                "col_id": best_col["id"],
                "continuation": is_continuation,
            }
            entry["sub_count"] = 1
            seen[slot_key] = entry

            if page == 0:
                col_slots_a[best_col["id"]].append(entry)
            else:
                col_slots_b[best_col["id"]].append(entry)
        else:
            # A3：同题号合并（原有逻辑）
            if slot_key in seen_slots_a:
                existing = seen_slots_a[slot_key]
                existing["score"] += s["score"]
                existing["sub_count"] = existing.get("sub_count", 1) + 1
                existing["heightRatio"] = max(existing["heightRatio"], hr)
                continue

            entry = {
                "slot_id": slot_key,
                "score": s["score"],
                "heightRatio": round(hr, 4),
                "page": page,
                "col_id": best_col["id"],
            }
            entry["sub_count"] = 1
            seen_slots_a[slot_key] = entry

            if page == 0:
                col_slots_a[best_col["id"]].append(entry)
            else:
                col_slots_b[best_col["id"]].append(entry)

    # ── 推算小问数量 ──
    def _infer_sub_count(entry: dict) -> int:
        sc = entry.get("sub_count", 1)
        if sc > 1:
            return sc
        # TQL 只有 1 个 slot 时，根据分值推算合理的小问数（约 2-3 分/小问）
        score = entry.get("score", 0)
        if entry.get("continuation"):
            return 0  # 续写区域不生成小问
        if score >= 10:
            return max(2, round(score / 2.5))
        if score >= 5:
            return 2
        return 0

    # ── 构建 essay regions ──
    def _make_regions(slot_list: list, side: str, col_idx: int, side_idx: int) -> list[dict]:
        if not slot_list:
            return []
        # 归一化 heightRatio
        total_hr = sum(e["heightRatio"] for e in slot_list)
        regions = []
        for e in slot_list:
            qno_str = e["slot_id"].replace("Q", "").replace("_", "")
            try:
                qno = int(qno_str)
                display_label = None
            except ValueError:
                qno = 0
                # 保留原始名称作为 displayLabel（去掉 Q 前缀，保留中文）
                display_label = e["slot_id"].replace("Q_", "").replace("Q", "")
            hr = e["heightRatio"] / total_hr if total_hr > 0 else 1.0
            is_cont = e.get("continuation", False)
            region: dict = {
                "id": f"essay-{e['slot_id']}{'-cont' if is_cont else ''}",
                "type": "essay",
                "qno": qno,
                "score": e["score"],
                "subs": _build_subs(
                    _infer_sub_count(e) if is_a4_dual else
                    (e.get("sub_count", 1) if e.get("sub_count", 1) > 1 else 0),
                    blanks_per_sub=2 if is_a4_dual else 3,
                ),
                "heightRatio": round(hr, 4),
                "_side": side, "_col": col_idx, "_sideIdx": side_idx,
            }
            if display_label:
                region["displayLabel"] = display_label
            if is_cont:
                region["continuation"] = True
            regions.append(region)
        return regions

    # ── fills 覆盖：SUBJECT_CONFIGS 指定的填空题从 essay slots 中移除 ──
    subject_cfg = SUBJECT_CONFIGS.get(subject_title, {})
    fills_cfg = subject_cfg.get("fills", {})
    fill_count = fills_cfg.get("count", 0)
    fill_start = fills_cfg.get("start", total_choices + 1)
    fill_per_row = fills_cfg.get("perRow", 2)

    if fill_count > 0:
        # 移除被 fills 覆盖的 slot（如英语 Q56 → 56-65 填空）
        fill_slot_id = f"Q{fill_start}"
        for cid in col_slots_a:
            col_slots_a[cid] = [e for e in col_slots_a[cid] if e["slot_id"] != fill_slot_id]
        seen_slots_a.pop(fill_slot_id, None)

    fill_regions = []
    for i in range(fill_count):
        qno = fill_start + i
        fill_regions.append({
            "id": f"fill-{qno}", "type": "fill", "qno": qno,
            "spaces": 1, "spaceWidth": "100%",
            "heightRatio": round(1 / max(fill_count, 1), 4),
            "_side": "A", "_col": 0, "_sideIdx": 0,
        })

    # ── A面 col 0: 固定区域 ──
    col0_regions: list[dict] = [
        {"id": "header", "type": "fixed", "role": "header",
         "_side": "A", "_col": 0, "_sideIdx": 0},
        {"id": "info", "type": "fixed", "role": "info",
         "_side": "A", "_col": 0, "_sideIdx": 0},
        {"id": "notice", "type": "fixed", "role": "notice",
         "_side": "A", "_col": 0, "_sideIdx": 0},
    ]
    if total_choices > 0:
        col0_regions.append({
            "id": "choices", "type": "fixed", "role": "choices",
            "count": total_choices, "options": max_options,
            "perRow": 20,
            "_side": "A", "_col": 0, "_sideIdx": 0,
        })

    # ── 组装 sides（按 TQL 栏数） ──
    col_ids = [c["id"] for c in columns]

    if is_a4_dual:
        # A4: 所有 essay 合并到 col 0（与 fixed 同栏）
        all_a_essays: list[dict] = []
        for cid in col_ids:
            all_a_essays.extend(_make_regions(col_slots_a.get(cid, []), "A", 0, 0))
        a_columns = [{"col": 0, "regions": col0_regions + fill_regions + all_a_essays}]

        all_b_essays: list[dict] = []
        for cid in col_ids:
            all_b_essays.extend(_make_regions(col_slots_b.get(cid, []), "B", 0, 1))
        b_columns = [{"col": 0, "regions": all_b_essays}]
    else:
        a_columns = [{"col": 0, "regions": col0_regions}]
        for i, cid in enumerate(col_ids):
            a_columns.append({
                "col": i + 1,
                "regions": _make_regions(col_slots_a.get(cid, []), "A", i + 1, 0),
            })

        has_b = any(len(v) > 0 for v in col_slots_b.values())
        b_columns = []
        for i, cid in enumerate(col_ids):
            b_columns.append({
                "col": i,
                "regions": _make_regions(col_slots_b.get(cid, []), "B", i, 1) if has_b else [],
            })

    # ── 组装 config ──
    full_config = dict(_BASE_STYLE)
    full_config.update({
        "subjectTitle": subject_title,
        "choiceCount": total_choices,
        "optionCount": max_options,
        "choicePerRow": 20,
        "choiceGroups": choice_groups,
        "fillCount": fill_count,
        "fillStart": fill_start,
        "fillPerRow": fill_per_row,
        "essayCount": len(seen_slots_a) + len(set(seen_slots_b.keys()) - set(seen_slots_a.keys())),
        "essayConfig": [{"score": e["score"]} for e in seen_slots_a.values()]
                      + [{"score": e["score"]} for k, e in seen_slots_b.items() if k not in seen_slots_a],
        "paperSize": paper_size,
    })

    return {
        "paper": paper_size,
        "config": full_config,
        "sides": [
            {"side": "A", "columns": a_columns},
            {"side": "B", "columns": b_columns},
        ],
    }


# ══════════════════════════════════════════════════════════════
# 查询接口
# ══════════════════════════════════════════════════════════════

_LAYOUT_CACHE: dict[str, dict] = {}

# TQL 模板文件路径映射（[141984xxx] 系列）
_TQL_BASE = "D:/试卷数据/YueXiaoEr/Scanner/Templetes"
_TQL_FILES: dict[str, str] = {
    "语文": f"{_TQL_BASE}/[141984001]语文.tpl",
    "数学": f"{_TQL_BASE}/[141984002]数学A.tpl",
    "英语": f"{_TQL_BASE}/[141984004]英语.tpl",
    "物理": f"{_TQL_BASE}/[141984005]物理A.tpl",
    "历史": f"{_TQL_BASE}/[141984007]历史.tpl",
    "化学": f"{_TQL_BASE}/[141984008]化学.tpl",
    "生物": f"{_TQL_BASE}/[141984009]生物.tpl",
    "政治": f"{_TQL_BASE}/[141984010]政治.tpl",
    "地理": f"{_TQL_BASE}/[141984011]地理.tpl",
}


def _resolve_tql_path(win_path: str) -> str:
    """跨平台路径：WSL 下 D:/x → /mnt/d/x，Windows 下原样返回。"""
    import platform
    if platform.system() != "Windows" and win_path[1:3] == ":/":
        drive = win_path[0].lower()
        return f"/mnt/{drive}/{win_path[3:]}"
    return win_path


def _normalize_subject(name: str) -> str:
    """物理A → 物理, 数学A → 数学。去掉尾部字母后缀匹配 TQL 文件名。"""
    import re
    return re.sub(r'[A-Za-z]+$', '', name).strip()


def get_default_layout(subject_name: str) -> dict:
    """按学科名返回默认编辑器布局——直接从 TQL 精确转换。"""
    if subject_name in _LAYOUT_CACHE:
        return _LAYOUT_CACHE[subject_name]

    # 先精确匹配，再去后缀匹配（"物理A" → "物理"），自动转 WSL 路径
    tql_path_raw = _TQL_FILES.get(subject_name) or _TQL_FILES.get(_normalize_subject(subject_name))
    if tql_path_raw:
        from pathlib import Path
        tql_path = _resolve_tql_path(tql_path_raw)
        if Path(tql_path).exists():
            layout = tql_to_editor_layout(tql_path, subject_title=subject_name)
            _LAYOUT_CACHE[subject_name] = layout
            return layout

    # TQL 文件不存在时 fallback：用 SUBJECT_CONFIGS 生成
    config = SUBJECT_CONFIGS.get(subject_name, SUBJECT_CONFIGS.get("数学", {}))
    sc = dict(config)
    sc["subjectTitle"] = subject_name
    layout = _fallback_layout(sc)
    _LAYOUT_CACHE[subject_name] = layout
    return layout


def _fallback_layout(config: dict) -> dict:
    """无 TQL 文件时的 fallback 布局生成（简化版）。"""
    choice_groups = config.get("choiceGroups", [])
    total_choices = sum(g["count"] for g in choice_groups)
    max_options = max((g["options"] for g in choice_groups), default=4)
    fills_cfg = config.get("fills", {})
    fill_count = fills_cfg.get("count", 0)
    fill_start = fills_cfg.get("start", total_choices + 1)
    fill_per_row = fills_cfg.get("perRow", 2)
    essays = config.get("essays", [])
    use_side_b = config.get("useSideB", False)

    col0_regions: list[dict] = [
        {"id": "header", "type": "fixed", "role": "header", "_side": "A", "_col": 0, "_sideIdx": 0},
        {"id": "info", "type": "fixed", "role": "info", "_side": "A", "_col": 0, "_sideIdx": 0},
        {"id": "notice", "type": "fixed", "role": "notice", "_side": "A", "_col": 0, "_sideIdx": 0},
    ]
    if total_choices > 0:
        col0_regions.append({
            "id": "choices", "type": "fixed", "role": "choices",
            "count": total_choices, "options": max_options, "perRow": 20,
            "_side": "A", "_col": 0, "_sideIdx": 0,
        })

    # fill regions（语法填空等）
    fill_regions = []
    for i in range(fill_count):
        qno = fill_start + i
        fill_regions.append({
            "id": f"fill-{qno}", "type": "fill", "qno": qno,
            "spaces": 1, "spaceWidth": "100%",
            "heightRatio": round(1 / max(fill_count, 1), 4),
            "_side": "A", "_col": 0, "_sideIdx": 0,
        })

    a_essays = [e for e in essays if e.get("page", 0) == 0]
    b_essays = [e for e in essays if e.get("page", 0) == 1]

    def _mk(lst: list, side: str, ci: int, si: int) -> list[dict]:
        if not lst:
            return []
        ts = sum(e["score"] for e in lst) or 1
        return [{
            "id": f"essay-{e['qno']}", "type": "essay", "qno": e["qno"],
            "score": e["score"], "subs": _build_subs(e.get("sub_count", 0)),
            "heightRatio": round(e["score"] / ts, 4),
            "_side": side, "_col": ci, "_sideIdx": si,
        } for e in lst]

    full_config = dict(_BASE_STYLE)

    # A4 双面判断：选择题多（>30）且有 B 面内容 → A4 双面
    is_a4 = (total_choices > 30 and use_side_b and b_essays)
    paper = "A4" if is_a4 else "A3"

    full_config.update({
        "subjectTitle": config.get("subjectTitle", ""),
        "choiceCount": total_choices, "optionCount": max_options,
        "choicePerRow": 20, "choiceGroups": choice_groups,
        "fillCount": fill_count, "fillStart": fill_start, "fillPerRow": fill_per_row,
        "essayCount": len(essays),
        "essayConfig": [{"score": e["score"]} for e in essays],
        "paperSize": paper,
    })

    if is_a4:
        # A4 双面：单栏布局，A/B 各一栏
        return {
            "paper": "A4", "config": full_config,
            "sides": [
                {"side": "A", "columns": [
                    {"col": 0, "regions": col0_regions + fill_regions + _mk(a_essays, "A", 0, 0)},
                ]},
                {"side": "B", "columns": [
                    {"col": 0, "regions": _mk(b_essays, "B", 0, 1)},
                ]},
            ],
        }

    # A3：3 栏布局
    s0 = [e for i, e in enumerate(a_essays) if i % 2 == 0]
    s1 = [e for i, e in enumerate(a_essays) if i % 2 == 1]

    return {
        "paper": "A3", "config": full_config,
        "sides": [
            {"side": "A", "columns": [
                {"col": 0, "regions": col0_regions},
                {"col": 1, "regions": _mk(s0, "A", 1, 0)},
                {"col": 2, "regions": _mk(s1, "A", 2, 0)},
            ]},
            {"side": "B", "columns": [
                {"col": 0, "regions": _mk(b_essays, "B", 0, 1)},
                {"col": 1, "regions": []},
                {"col": 2, "regions": []},
            ]},
        ],
    }
