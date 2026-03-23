"""答题卡骨架 → paper-seg 兼容的切割模板 JSON。"""
from __future__ import annotations


def skeleton_to_paperseg_json(
    skeleton: dict,
    layout: dict,
    exam_id: str,
    subject: str,
    side: str = "A",
    question_map: dict[str, str] | None = None,
) -> dict:
    """将 skeleton + layout 转换为 paper-seg 模板 JSON。

    Args:
        skeleton: build_skeleton_from_spec() 输出
        layout: allocate_by_weights() 输出
        exam_id: 考试 ID
        subject: 科目名
        side: 面（A/B）

    Returns:
        paper-seg 兼容的模板 JSON
    """
    # Anchors: {id, rect} → {id, cx, cy, x, y, w, h}
    anchors = []
    for a in skeleton.get("anchors", []):
        r = a["rect"]
        w = r["x2"] - r["x1"]
        h = r["y2"] - r["y1"]
        anchors.append({
            "id": a["id"],
            "cx": r["x1"] + w // 2,
            "cy": r["y1"] + h // 2,
            "x": r["x1"],
            "y": r["y1"],
            "w": w,
            "h": h,
        })

    # Regions
    regions = []

    # 选择题组 → choice_group
    for g in skeleton.get("objective_groups", []):
        region = {
            "id": g["group_id"],
            "name": g["group_id"],
            "type": "choice_group",
            "rect": dict(g["rect"]),
            "page": 0,
            "score": 0,
            "rows": g["count"],
            "cols": g["options"],
            "labels": g.get("symbols", "A,B,C,D").split(","),
            "multi_select": g.get("multi_select", False),
        }
        if question_map:
            # 为每道选择题生成独立的 question_id 映射列表
            # question_map key 可以是组 ID 或题号字符串
            start_no = g.get("start_no", 1)
            per_question_ids = []
            for i in range(g["count"]):
                qno = str(start_no + i)
                per_question_ids.append(question_map.get(qno))
            if any(per_question_ids):
                region["question_ids"] = per_question_ids
            # 组级别也保留（向后兼容）
            if g["group_id"] in question_map:
                region["question_id"] = question_map[g["group_id"]]
        regions.append(region)

    # 考号涂卡 → number_fill
    exam_num = skeleton.get("exam_number_area")
    if exam_num:
        regions.append({
            "id": "exam_number",
            "name": "准考证号",
            "type": "number_fill",
            "rect": dict(exam_num["rect"]),
            "page": 0,
            "num_columns": exam_num["digits"],
            "symbols": "0123456789",
        })

    # 主观题 → subjective
    for slot in layout.get("slots", []):
        for sr in slot.get("sub_regions", []):
            region = {
                "id": sr["id"],
                "name": sr["name"],
                "type": "subjective",
                "rect": dict(sr["rect"]),
                "page": slot.get("inpage", 0),
                "score": sr.get("score", 0),
            }
            if question_map and sr["name"] in question_map:
                region["question_id"] = question_map[sr["name"]]
            regions.append(region)

    return {
        "version": "1.0",
        "exam_id": exam_id,
        "subject": subject,
        "side": side,
        "image_size": {
            "width": skeleton["image_width"],
            "height": skeleton["image_height"],
        },
        "anchors": anchors,
        "regions": regions,
    }
