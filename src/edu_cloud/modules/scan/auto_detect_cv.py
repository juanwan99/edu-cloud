"""答题卡 region OpenCV 几何检测 + LLM 语义标注（混合方案）。

OpenCV 负责精确像素坐标，LLM 只做分类和语义标签（qno/score/type）。
输出 type="subjective" 以兼容 pipeline_service 的切割过滤。
"""
import base64
import json
import logging
import re
from pathlib import Path

import cv2
import numpy as np
import httpx
from PIL import Image
from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from edu_cloud.config import settings

LLM_PROXY_URL = f"{settings.LLM_API_URL}/chat/completions"
SLOT = "answer-vision"
FRONTEND_DIST = Path("frontend/dist").resolve()

LABEL_PROMPT = """你是答题卡结构分析专家。OpenCV 已在这张答题卡上检测出 {N} 个矩形区域，坐标和特征如下：

{REGION_LIST}

图片尺寸：{W} × {H} 像素。

请为每个区域分类并标注语义信息。返回 JSON（不要 markdown 围栏）：
{{"regions":[{{"id":"R01","type":"choice_group","rows":16,"cols":4,"start_no":1,"qg_indexno":1,"score":3}},{{"id":"R02","type":"essay","qno":17,"score":10}},{{"id":"R03","type":"barcode"}},{{"id":"R04","type":"not_a_region"}}]}}

四种类型：

1. choice_group — 选择题涂卡区
   识别特征：区域内有 A B C D（或 A B C D E）字母标记、规则排列的小圆圈/气泡、题号列表（1 2 3...）。
   即使气泡已被学生涂黑，仍然是 choice_group。
   补充字段: rows(题数), cols(选项数 3-5), start_no(起始题号), qg_indexno(组序号从1开始), score(每题分数,无法判断则0)

2. essay — 主观题/解答题作答区域
   识别特征：大面积空白/横线供书写，顶部通常有题号和分值标注。
   单题: {{"qno":17,"score":10}}
   多题合框: {{"qnos":[3,4,5],"scores":[4,4,6],"splits":[0,0.25,0.55,1.0]}}
   splits 按实际答题空间比例估算，不要平均分。

3. barcode — 学生信息区（条形码/二维码 + 姓名 + 准考证号），每卡通常 1 个

4. not_a_region — 非作答区（标题/定位黑块/注意事项/缺考标记）

重要规则：
- 选择题涂卡区必须标 choice_group，不要标成 essay。看到 A B C D 字母排列 = choice_group。
- 同一大题被栏线分割为多个区域时，所有区域用相同 qno
- 区域顶部有说明文字但下方有空白答题区 → essay，不是 not_a_region
- 每个 R?? 必须出现在输出中
- 选择题起始题号通常为 1
- 仔细阅读题号和分值标注，确保 qno 和 score 准确"""


SIDE_B_CONTEXT = """

补充上下文：这是答题卡的 B 面（背面）。A 面已检测到以下区域：
{A_SIDE_SUMMARY}
B 面的题号应该是 A 面的延续，不要从 1 重新开始。"""


class AutoDetectCVRequest(BaseModel):
    image_path: str
    min_area_ratio: float = 0.008
    skip_llm: bool = False
    prior_regions: list[dict] | None = None


def _resolve_image(p: str) -> Path:
    p = p.strip()
    if p.startswith("/samples/"):
        return FRONTEND_DIST / p.lstrip("/")
    if p.startswith("/uploads/"):
        return Path(settings.UPLOAD_DIR).resolve() / p.split("/uploads/", 1)[1]
    if p.startswith("/"):
        return Path(p)
    raise HTTPException(400, f"image_path 必须是绝对路径: {p}")


def _detect_rects_core(
    gray: np.ndarray, min_area_ratio: float,
    dilate_iters: int, use_bbox_area: bool,
) -> list[dict]:
    h, w = gray.shape
    total_area = h * w
    min_area = total_area * min_area_ratio

    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    if dilate_iters > 0:
        kern_d = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.dilate(binary, kern_d, iterations=dilate_iters)
    kern_c = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kern_c)

    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rects = []
    for cnt in contours:
        x, y, rw, rh = cv2.boundingRect(cnt)
        area = (rw * rh) if use_bbox_area else cv2.contourArea(cnt)
        if area < min_area or area > total_area * 0.85:
            continue
        if rw < 50 or rh < 50:
            continue
        aspect = rw / rh
        if aspect < 0.15 or aspect > 7:
            continue
        rects.append({"x": x, "y": y, "w": rw, "h": rh, "area": rw * rh})
    return rects


def _detect_rectangles(gray: np.ndarray, min_area_ratio: float) -> list[dict]:
    # Pass 1: no dilation, contourArea (thick borders)
    rects1 = _detect_rects_core(gray, min_area_ratio, dilate_iters=0, use_bbox_area=False)
    # Pass 2: dilation + bboxArea (thin borders)
    rects2 = _detect_rects_core(gray, min_area_ratio, dilate_iters=2, use_bbox_area=True)

    if len(rects1) < 2:
        rects = rects2
    else:
        # Merge: keep all from pass1, add pass2 rects that don't overlap
        rects = list(rects1)
        for r2 in rects2:
            dominated = False
            for r1 in rects1:
                ox = max(0, min(r2["x"]+r2["w"], r1["x"]+r1["w"]) - max(r2["x"], r1["x"]))
                oy = max(0, min(r2["y"]+r2["h"], r1["y"]+r1["h"]) - max(r2["y"], r1["y"]))
                if ox * oy > min(r2["w"]*r2["h"], r1["w"]*r1["h"]) * 0.3:
                    dominated = True
                    break
            if not dominated:
                rects.append(r2)

    # Remove containers: if rect i fully contains rect j, drop i (keep leaf)
    n = len(rects)
    has_child = [False] * n
    margin = 20
    for i in range(n):
        ri = rects[i]
        for j in range(n):
            if i == j:
                continue
            rj = rects[j]
            if (rj["x"] >= ri["x"] - margin
                and rj["y"] >= ri["y"] - margin
                and rj["x"] + rj["w"] <= ri["x"] + ri["w"] + margin
                and rj["y"] + rj["h"] <= ri["y"] + ri["h"] + margin
                and rj["area"] < ri["area"] * 0.85):
                has_child[i] = True
                break
    rects = [r for r, hc in zip(rects, has_child) if not hc]

    # Dedupe: merge rects with >70% mutual overlap (different contour paths for same box)
    merged = []
    used = [False] * len(rects)
    for i, ri in enumerate(rects):
        if used[i]:
            continue
        group = [ri]
        for j in range(i + 1, len(rects)):
            if used[j]:
                continue
            rj = rects[j]
            ox = max(0, min(ri["x"]+ri["w"], rj["x"]+rj["w"]) - max(ri["x"], rj["x"]))
            oy = max(0, min(ri["y"]+ri["h"], rj["y"]+rj["h"]) - max(ri["y"], rj["y"]))
            overlap = ox * oy
            smaller = min(ri["w"]*ri["h"], rj["w"]*rj["h"])
            if smaller > 0 and overlap / smaller > 0.7:
                group.append(rj)
                used[j] = True
        # Keep the one with largest area
        best = max(group, key=lambda r: r["area"])
        merged.append(best)
        used[i] = True

    merged.sort(key=lambda r: (r["y"] // 80, r["x"]))
    return merged


def _detect_bubbles(gray: np.ndarray, rect: dict) -> dict | None:
    x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
    crop = gray[y:y+h, x:x+w]
    _, binary = cv2.threshold(crop, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bubble_ys = []
    bubble_xs = []
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw < 6 or bh < 6 or bw > 55 or bh > 55:
            continue
        if bw / bh < 0.35 or bw / bh > 2.8:
            continue
        area = cv2.contourArea(cnt)
        if area < 20:
            continue
        peri = cv2.arcLength(cnt, True)
        if peri == 0:
            continue
        circ = 4 * 3.14159 * area / (peri * peri)
        if circ < 0.25:
            continue
        bubble_ys.append(by + bh // 2)
        bubble_xs.append(bx + bw // 2)

    if len(bubble_ys) < 8:
        return None

    # Cluster by y → rows
    ys = sorted(bubble_ys)
    rows = [[ys[0]]]
    for yv in ys[1:]:
        if yv - rows[-1][-1] < 18:
            rows[-1].append(yv)
        else:
            rows.append([yv])

    from collections import Counter
    counts = Counter(len(r) for r in rows)
    cols = counts.most_common(1)[0][0]
    valid = sum(1 for r in rows if abs(len(r) - cols) <= 1)

    if valid < 3 or cols < 3:
        return None
    return {"rows": valid, "cols": cols}


def _find_split_lines(
    gray: np.ndarray, x1: int, y1: int, x2: int, y2: int, n_parts: int
) -> list[int]:
    """Detect horizontal dividing lines within a region to split into n_parts.
    Returns n_parts+1 y-coordinates (including top and bottom edges)."""
    crop = gray[y1:y2, x1:x2]
    h, w = crop.shape

    _, binary = cv2.threshold(crop, 200, 255, cv2.THRESH_BINARY_INV)

    # Morphological opening with wide horizontal kernel → isolate horizontal lines
    kern_w = max(w // 3, 100)
    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (kern_w, 1))
    lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kern)

    # Project horizontally: sum each row
    row_sum = np.sum(lines_img, axis=1)
    threshold = w * 0.5 * 255

    # Find rows with strong horizontal lines (must span >50% of width)
    line_rows = np.where(row_sum > threshold)[0]

    if len(line_rows) == 0:
        # Fallback: equal split
        return [y1 + h * i // n_parts for i in range(n_parts)] + [y2]

    # Cluster consecutive rows into line centers
    centers = []
    start = line_rows[0]
    for j in range(1, len(line_rows)):
        if line_rows[j] - line_rows[j - 1] > 5:
            centers.append((start + line_rows[j - 1]) // 2)
            start = line_rows[j]
    centers.append((start + line_rows[-1]) // 2)

    # Filter: skip lines too close to edges (10%) and too close to each other (8%)
    margin = h * 0.10
    min_gap = h * 0.08
    centers = [c for c in centers if margin < c < h - margin]
    # Remove lines too close together (keep the one closer to ideal position)
    if len(centers) > 1:
        filtered = [centers[0]]
        for c in centers[1:]:
            if c - filtered[-1] >= min_gap:
                filtered.append(c)
        centers = filtered

    # We need exactly n_parts-1 split lines
    if len(centers) >= n_parts - 1:
        # Pick the n_parts-1 most evenly spaced ones
        centers.sort()
        if len(centers) == n_parts - 1:
            picks = centers
        else:
            # Greedy: pick lines closest to ideal equal-split positions
            ideal = [h * (i + 1) // n_parts for i in range(n_parts - 1)]
            used = set()
            picks = []
            for target in ideal:
                best = min(
                    (c for c in centers if c not in used),
                    key=lambda c: abs(c - target),
                )
                picks.append(best)
                used.add(best)
            picks.sort()
    else:
        # Not enough lines detected, fill gaps with equal split
        picks = list(centers)
        while len(picks) < n_parts - 1:
            # Find the largest gap and split it
            all_pts = [0] + sorted(picks) + [h]
            gaps = [(all_pts[j + 1] - all_pts[j], j) for j in range(len(all_pts) - 1)]
            gaps.sort(reverse=True)
            _, gi = gaps[0]
            mid = (all_pts[gi] + all_pts[gi + 1]) // 2
            picks.append(mid)
        picks.sort()

    return [y1] + [y1 + p for p in picks] + [y2]


def _detect_barcode(gray: np.ndarray) -> list[dict]:
    """Detect barcode regions using pyzbar. Returns generous bounding boxes."""
    try:
        from pyzbar import pyzbar
    except ImportError:
        logger.warning("pyzbar not installed, skip barcode detection")
        return []

    h, w = gray.shape
    decoded = pyzbar.decode(gray)
    if not decoded:
        return []

    results = []
    for d in decoded:
        bx, by, bw, bh = d.rect
        # Extend region to cover student info above barcode
        pad_x = bw // 3
        pad_up = bh * 3
        pad_down = bh // 2
        region = {
            "x": max(0, bx - pad_x),
            "y": max(0, by - pad_up),
            "w": min(w, bw + pad_x * 2),
            "h": min(h - max(0, by - pad_up), bh + pad_up + pad_down),
            "barcode_data": d.data.decode("utf-8", errors="replace"),
            "barcode_type": d.type,
        }
        results.append(region)
        logger.info("barcode found: %s type=%s at (%d,%d)", region["barcode_data"][:20], d.type, bx, by)

    return results


async def _llm_label(
    img_path: Path, rects: list[dict], w: int, h: int, bubble_hints: dict,
    prior_regions: list[dict] | None = None,
) -> tuple[list[dict], str]:
    lines = []
    for i, r in enumerate(rects):
        rid = f"R{i+1:02d}"
        hint = ""
        if i in bubble_hints:
            bh = bubble_hints[i]
            hint = f" [OpenCV检测到{bh['rows']}行×{bh['cols']}列气泡阵列]"
        lines.append(
            f"  {rid}: pos=({r['x']},{r['y']}) size={r['w']}×{r['h']}{hint}"
        )

    prompt = LABEL_PROMPT.format(
        N=len(rects), REGION_LIST="\n".join(lines), W=w, H=h
    )

    if prior_regions:
        summary_parts = []
        for pr in prior_regions:
            t = pr.get("type", "")
            rid = pr.get("id", f"R{len(summary_parts)+1:02d}")
            if t == "choice_group":
                summary_parts.append(f'{rid}: 选择题 Q{pr.get("start_no",1)}-Q{pr.get("start_no",1)+pr.get("rows",0)-1}')
            elif t == "subjective":
                summary_parts.append(f'{rid}: 主观题 Q{pr.get("qno","?")} ({pr.get("score",0)}分)')
        prompt += SIDE_B_CONTEXT.format(A_SIDE_SUMMARY="\n".join(summary_parts))

    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    body = {
        "model": "gemini-3.0-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                LLM_PROXY_URL, json=body, headers={"X-LLM-Slot": SLOT}
            )
        except httpx.TimeoutException:
            logger.warning("LLM label timeout")
            return [], "timeout"

    if resp.status_code != 200:
        logger.warning("LLM label %d: %s", resp.status_code, resp.text[:300])
        return [], f"http_{resp.status_code}"

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return [], "bad_response"

    text = content.strip()
    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL
        ).strip()
    def _try_parse(s: str):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Try fixing truncated JSON by closing brackets
        for suffix in ["]}", "]}}", '"]}'  , '"]}']:
            try:
                return json.loads(s + suffix)
            except json.JSONDecodeError:
                continue
        return None

    parsed = _try_parse(text)
    if parsed is None:
        m = re.search(r"\{[\s\S]*", text)
        if m:
            parsed = _try_parse(m.group(0))
        if parsed is None:
            return [], "json_fail"

    if isinstance(parsed, list):
        regions = parsed
    elif isinstance(parsed, dict):
        regions = parsed.get("regions", [])
    else:
        return [], "unexpected_type"

    # Filter out Gemini native format entries (box_2d) — we only want R01-style
    regions = [r for r in regions if r.get("id", "").startswith("R")]

    return regions, content[:1500]


def _build_opencv_only(
    rects: list[dict],
    barcode_rects: list[dict],
    bubble_hints: dict[int, dict],
    w: int, h: int,
) -> dict:
    """纯 OpenCV 启发式分类，不调 LLM。"""
    barcode_set = set()
    for br in barcode_rects:
        for i, r in enumerate(rects):
            iou_x = max(0, min(r["x"]+r["w"], br["x"]+br["w"]) - max(r["x"], br["x"]))
            iou_y = max(0, min(r["y"]+r["h"], br["y"]+br["h"]) - max(r["y"], br["y"]))
            if iou_x > 0 and iou_y > 0:
                overlap = iou_x * iou_y
                if overlap > br["w"] * br["h"] * 0.3:
                    barcode_set.add(i)

    result = []
    qno_counter = 1
    cg_counter = 1

    sorted_indices = sorted(range(len(rects)), key=lambda i: (rects[i]["y"], rects[i]["x"]))

    for i in sorted_indices:
        r = rects[i]
        rid = f"R{i+1:02d}"
        rect = {"x1": r["x"], "y1": r["y"], "x2": r["x"]+r["w"], "y2": r["y"]+r["h"]}
        area = r["w"] * r["h"]
        img_area = w * h

        if i in barcode_set:
            result.append({"id": rid, "type": "barcode", "rect": rect})
            continue

        if area < img_area * 0.005:
            continue

        if i in bubble_hints:
            bh = bubble_hints[i]
            result.append({
                "id": rid,
                "type": "choice_group",
                "rect": rect,
                "rows": bh["rows"],
                "cols": bh["cols"],
                "start_no": qno_counter,
                "qg_indexno": cg_counter,
                "score": 0,
            })
            qno_counter += bh["rows"]
            cg_counter += 1
        else:
            result.append({
                "id": rid,
                "type": "subjective",
                "question_type": "essay",
                "qno": qno_counter,
                "score": 0,
                "rect": rect,
            })
            qno_counter += 1

    if barcode_rects and not barcode_set:
        br = barcode_rects[0]
        result.append({
            "id": f"BC01",
            "type": "barcode",
            "rect": {"x1": br["x"], "y1": br["y"], "x2": br["x"]+br["w"], "y2": br["y"]+br["h"]},
        })

    stats = (f"opencv:{len(rects)}rects,"
             f"{sum(1 for i in range(len(rects)) if i in bubble_hints)}bubbles,"
             f"{len(barcode_rects)}barcodes; out:{len(result)}")
    logger.info("auto_detect_cv done (opencv-only): %s", stats)

    return {
        "regions": result,
        "width": w,
        "height": h,
        "method": "opencv-only",
        "raw": stats,
    }


async def auto_detect_cv_regions(req: AutoDetectCVRequest) -> dict:
    img_path = _resolve_image(req.image_path)
    if not img_path.is_file():
        raise HTTPException(404, f"图片不存在: {img_path}")

    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        pil_img = Image.open(img_path).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    rects = _detect_rectangles(gray, req.min_area_ratio)
    # Barcode detection (pyzbar, independent of contour detection)
    barcode_rects = _detect_barcode(gray)
    logger.info("auto_detect_cv: %s %dx%d → %d rects, %d barcodes", img_path.name, w, h, len(rects), len(barcode_rects))

    if not rects and not barcode_rects:
        # 有 prior_regions（B 面）时，检查页面是否有实际内容再 fallback
        has_content = False
        if req.prior_regions:
            _, bw = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            dark_ratio = np.count_nonzero(bw) / (w * h)
            has_content = dark_ratio > 0.02
            logger.info("auto_detect_cv: B-side content check: dark_ratio=%.4f has_content=%s", dark_ratio, has_content)

        if not has_content:
            return {
                "regions": [],
                "width": w,
                "height": h,
                "method": "opencv+llm",
                "raw": "no rects",
            }
        # B 面 fallback：OpenCV 检测不到矩形框（如写作虚线格纸），
        # 将整页（去页边距）作为一个区域交给 LLM 判断
        margin_x, margin_y = int(w * 0.05), int(h * 0.04)
        rects = [{"x": margin_x, "y": margin_y, "w": w - margin_x * 2, "h": h - margin_y * 2, "area": 0}]
        logger.info("auto_detect_cv: B-side fallback, using full-page rect")

    bubble_hints: dict[int, dict] = {}
    for i, r in enumerate(rects):
        bh = _detect_bubbles(gray, r)
        if bh:
            bubble_hints[i] = bh
            logger.info("  R%02d bubble: %dx%d", i + 1, bh["rows"], bh["cols"])

    if req.skip_llm:
        return _build_opencv_only(rects, barcode_rects, bubble_hints, w, h)

    labels, raw_content = await _llm_label(img_path, rects, w, h, bubble_hints, req.prior_regions)
    label_map = {l.get("id", ""): l for l in labels}

    result = []
    for i, r in enumerate(rects):
        rid = f"R{i+1:02d}"
        lbl = label_map.get(rid, {})
        rtype = lbl.get("type", "not_a_region")
        if rtype == "not_a_region":
            continue

        region = {
            "id": rid,
            "rect": {
                "x1": r["x"],
                "y1": r["y"],
                "x2": r["x"] + r["w"],
                "y2": r["y"] + r["h"],
            },
        }

        if rtype == "choice_group":
            region["type"] = "choice_group"
            bh = bubble_hints.get(i, {})
            region["rows"] = lbl.get("rows") or bh.get("rows", 10)
            region["cols"] = lbl.get("cols") or bh.get("cols", 4)
            region["start_no"] = lbl.get("start_no", 1)
            region["qg_indexno"] = lbl.get("qg_indexno", 1)
            region["score"] = lbl.get("score", 0)
        elif rtype == "barcode":
            region["type"] = "barcode"
        else:
            qnos = lbl.get("qnos")
            scores = lbl.get("scores", [])
            if qnos and len(qnos) > 1:
                rect = region["rect"]
                total_h = rect["y2"] - rect["y1"]
                # Use LLM-provided splits, fall back to OpenCV lines, then equal
                llm_splits = lbl.get("splits")
                if llm_splits and len(llm_splits) == len(qnos) + 1:
                    y_splits = [rect["y1"] + int(s * total_h) for s in llm_splits]
                else:
                    y_splits = _find_split_lines(
                        gray, rect["x1"], rect["y1"], rect["x2"], rect["y2"], len(qnos)
                    )
                for qi, qno in enumerate(qnos):
                    sub = {
                        "id": f"R{i+1:02d}-{qi+1}",
                        "type": "subjective",
                        "question_type": "essay",
                        "qno": qno,
                        "score": scores[qi] if qi < len(scores) else 0,
                        "rect": {
                            "x1": rect["x1"],
                            "y1": y_splits[qi],
                            "x2": rect["x2"],
                            "y2": y_splits[qi + 1],
                        },
                    }
                    result.append(sub)
                continue
            region["type"] = "subjective"
            region["question_type"] = "essay"
            region["qno"] = lbl.get("qno", 0)
            region["score"] = lbl.get("score", 0)

        result.append(region)

    # Merge horizontally adjacent regions with same qno (composition/作文)
    from collections import Counter, defaultdict
    qno_groups: dict[int, list] = defaultdict(list)
    for r in result:
        if r.get("type") == "subjective" and r.get("qno"):
            qno_groups[r["qno"]].append(r)

    merged_ids = set()
    for qno, group in qno_groups.items():
        if len(group) < 2:
            continue
        # Check if regions are horizontally adjacent (similar y range, different x)
        rects_sorted = sorted(group, key=lambda r: r["rect"]["x1"])
        y_ranges = [(r["rect"]["y1"], r["rect"]["y2"]) for r in rects_sorted]
        # Adjacent if y-ranges overlap significantly
        all_adjacent = True
        for j in range(1, len(rects_sorted)):
            y_overlap = min(y_ranges[j][1], y_ranges[j-1][1]) - max(y_ranges[j][0], y_ranges[j-1][0])
            avg_h = ((y_ranges[j][1]-y_ranges[j][0]) + (y_ranges[j-1][1]-y_ranges[j-1][0])) / 2
            if y_overlap < avg_h * 0.5:
                all_adjacent = False
                break
        if all_adjacent:
            # Merge into one bounding box
            merged_rect = {
                "x1": min(r["rect"]["x1"] for r in group),
                "y1": min(r["rect"]["y1"] for r in group),
                "x2": max(r["rect"]["x2"] for r in group),
                "y2": max(r["rect"]["y2"] for r in group),
            }
            total_score = sum(r.get("score", 0) for r in group)
            group[0]["rect"] = merged_rect
            group[0]["score"] = total_score
            group[0]["id"] = f"Q{qno}"
            for r in group[1:]:
                merged_ids.add(id(r))

    result = [r for r in result if id(r) not in merged_ids]

    # Handle remaining duplicate qno: rename IDs to Q17-1, Q17-2
    qno_count: dict[int, int] = Counter()
    for r in result:
        if r.get("qno"):
            qno_count[r["qno"]] += 1
    for r in result:
        qno = r.get("qno")
        if qno and qno_count[qno] > 1:
            seq = sum(1 for prev in result if prev.get("qno") == qno and id(prev) <= id(r))
            r["id"] = f"Q{qno}-{seq}"

    cgs = sorted(
        [r for r in result if r["type"] == "choice_group"],
        key=lambda x: x.get("qg_indexno", 0),
    )
    essays = sorted(
        [r for r in result if r["type"] == "subjective"],
        key=lambda x: x.get("qno", 0),
    )
    barcodes_llm = [r for r in result if r["type"] == "barcode"]
    # Add pyzbar-detected barcodes (not from LLM)
    bc_regions = []
    for i, bc in enumerate(barcode_rects):
        bc_regions.append({
            "id": f"BC{i+1:02d}",
            "type": "barcode",
            "rect": {"x1": bc["x"], "y1": bc["y"], "x2": bc["x"] + bc["w"], "y2": bc["y"] + bc["h"]},
            "barcode_data": bc.get("barcode_data", ""),
            "barcode_type": bc.get("barcode_type", ""),
        })
    all_barcodes = bc_regions + barcodes_llm
    result = all_barcodes + cgs + essays

    info = (
        f"opencv:{len(rects)}rects,{len(bubble_hints)}bubbles,{len(barcode_rects)}barcodes; "
        f"llm:{len(labels)}labels; out:{len(result)}"
    )
    logger.info("auto_detect_cv done: %s", info)
    return {
        "regions": result,
        "width": w,
        "height": h,
        "method": "opencv+llm",
        "raw": info,
    }
