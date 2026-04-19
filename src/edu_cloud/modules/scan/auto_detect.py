"""答题卡 region AI 预识别端点（附加到 pipeline_router）。"""
import base64
import json
import logging
import os
import re
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

LLM_PROXY_URL = "http://127.0.0.1:8100/v1/chat/completions"
SLOT = "answer-vision"
FRONTEND_DIST = Path("/home/ops/projects/edu-cloud/frontend/dist")
UPLOADS_ROOT = Path("/home/ops/projects/edu-cloud/uploads")

PROMPT = """你是答题卡结构识别专家。识别扫描件上**学生作答的区域**，返回 JSON。

图像尺寸：{W} × {H} 像素，原点 (0,0) 在左上角。

【输出格式】
严格 JSON，只返回 {"regions":[...]}，不要 markdown 或解释。
每个 region 的 rect **必须是对象格式** {"x1":int,"y1":int,"x2":int,"y2":int}，绝对不要用数组。
坐标是**原图实际像素值**（x ∈ [0, {W}], y ∈ [0, {H}]），不要归一化到 0-1000 或其他空间。

【区域类型】
A) choice_group = 真正的选择题气泡阵列
   必要特征：必须能看到成行排列的圆形/椭圆气泡，每题 4-5 个并列，通常带题号 1,2,3...
   额外字段：rows=题数, cols=选项数, start_no=该组首题号, qg_indexno=组序(从1递增)
B) essay = 主观题/问答题作答区
   额外字段：qno=题号(大题号整数，如 17), score=该题满分(题号旁"X分"字样)

【禁止标注的非答题区（严格排除）】
- 四角定位黑方块 / 定位线
- 考生信息栏：姓名/班级/座位号/考场号 的填写或填涂区
- 准考证号条形码 / 条形码区域
- 学号 0-9 的填涂涂卡（即使看起来像选择题气泡，也是信息区，不标）
- 缺考标记 / 违纪标记
- "请在各题答题区域内作答"等说明文字
- 分数登记表 / 评卷员签名栏

【关键约束：一题一框】
主观题每道大题（qno=17, 18, 19, 20...）**只输出 1 个 rect**，rect 必须覆盖该题所有子问题 (1)(2)(3) 的作答区域。
不要为子题 (1)(2)(3) 分别输出 rect，合并为外接矩形。
如果一道题跨多栏或多行，用 bounding box 把所有作答块包裹成一个大矩形。

【示例】
卡面左侧上部是条形码+姓名+学号填涂 → 忽略
卡面中部是 20 题选择题的气泡阵列 → choice_group rows=20 cols=4 start_no=1
卡面下部/右侧是 21、22、23 题主观题，21 题有 (1)(2) 两个子题 → 3 个 essay rect（21 合并 (1)(2)）
"""


class AutoDetectRequest(BaseModel):
    image_path: str  # /samples/xx.png 或绝对路径


class AutoDetectResponse(BaseModel):
    regions: list
    width: int
    height: int
    raw: str | None = None


def _resolve_image(p: str) -> Path:
    p = p.strip()
    if p.startswith("/samples/"):
        return FRONTEND_DIST / p.lstrip("/")
    if p.startswith("/uploads/"):
        return Path("/home/ops/projects/edu-cloud") / p.lstrip("/")
    if p.startswith("/"):
        # 绝对路径白名单：仅允许 edu-cloud 项目下
        ap = Path(p)
        if str(ap).startswith("/home/ops/projects/edu-cloud/"):
            return ap
    raise HTTPException(400, f"image_path 不在白名单: {p}")


async def auto_detect_regions(req: AutoDetectRequest) -> dict:
    img_path = _resolve_image(req.image_path)
    if not img_path.is_file():
        raise HTTPException(404, f"图片不存在: {img_path}")

    # 读图并取尺寸
    from PIL import Image
    with Image.open(img_path) as im:
        w, h = im.size

    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    prompt_text = PROMPT.replace("{W}", str(w)).replace("{H}", str(h))
    body = {
        "model": "gemini-3-pro-preview",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "temperature": 0,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    headers = {"X-LLM-Slot": SLOT, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(LLM_PROXY_URL, json=body, headers=headers)
        except httpx.TimeoutException:
            raise HTTPException(504, "LLM vision 调用超时")
    if resp.status_code != 200:
        raise HTTPException(502, f"LLM proxy 返回 {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, f"LLM 响应结构异常: {str(data)[:400]}")

    # 去掉 markdown fence
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        # 再尝试抓最大 {} 块
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                raise HTTPException(502, f"LLM JSON 解析失败: {e} / raw={text[:400]}")
        else:
            raise HTTPException(502, f"LLM 未返回 JSON: {text[:400]}")

    regions = parsed.get("regions") or []

    # 坐标 clamp —— 兼容 rect 为 {x1,y1,x2,y2} 或 [x1,y1,x2,y2] 两种格式
    # 另兼容 Gemini 的 [ymin,xmin,ymax,xmax] 0-1000 归一化空间
    clean = []
    raw_rects: list[tuple[int,int,int,int]] = []
    for r in regions:
        rect = r.get("rect") or r.get("bbox") or r.get("box")
        try:
            if isinstance(rect, list) and len(rect) >= 4:
                # Gemini 标准是 [ymin, xmin, ymax, xmax] —— 按此解析
                y1, x1, y2, x2 = rect[0], rect[1], rect[2], rect[3]
            elif isinstance(rect, dict):
                x1 = rect.get("x1", rect.get("left", rect.get("xmin")))
                y1 = rect.get("y1", rect.get("top", rect.get("ymin")))
                x2 = rect.get("x2", rect.get("right", rect.get("xmax")))
                y2 = rect.get("y2", rect.get("bottom", rect.get("ymax")))
            else:
                continue
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        except (TypeError, ValueError, KeyError):
            continue
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        raw_rects.append((x1, y1, x2, y2))
        r["_raw_rect"] = (x1, y1, x2, y2)
        clean.append(r)

    # 判定是否归一化（Gemini 返回 0-1000 空间）：若所有坐标最大值 ≤ 1024 且 W/H 明显大于此，则认为归一化
    if raw_rects:
        mx = max(max(x1, y1, x2, y2) for (x1, y1, x2, y2) in raw_rects)
        is_normalized = mx <= 1024 and (w > 1024 or h > 1024)
    else:
        is_normalized = False

    for r in clean:
        x1, y1, x2, y2 = r.pop("_raw_rect")
        if is_normalized:
            # Gemini 0-1000 空间还原
            sx, sy = w / 1000.0, h / 1000.0
            x1 = int(x1 * sx); x2 = int(x2 * sx)
            y1 = int(y1 * sy); y2 = int(y2 * sy)
        x1 = max(0, min(w, x1)); y1 = max(0, min(h, y1))
        x2 = max(0, min(w, x2)); y2 = max(0, min(h, y2))
        r["rect"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    # 再过滤过小矩形
    clean = [r for r in clean if (r["rect"]["x2"]-r["rect"]["x1"] >= 20 and r["rect"]["y2"]-r["rect"]["y1"] >= 20)]

    # 后处理：按 qno 合并同号子题的 bounding box
    merged: dict[int, dict] = {}
    choice_groups: list[dict] = []
    for r in clean:
        if r.get("type") == "essay":
            qno = r.get("qno")
            if qno is None:
                continue
            if qno in merged:
                rect = merged[qno]["rect"]
                rect["x1"] = min(rect["x1"], r["rect"]["x1"])
                rect["y1"] = min(rect["y1"], r["rect"]["y1"])
                rect["x2"] = max(rect["x2"], r["rect"]["x2"])
                rect["y2"] = max(rect["y2"], r["rect"]["y2"])
                # score 取最大 (若子题给分)
                if (r.get("score") or 0) > (merged[qno].get("score") or 0):
                    merged[qno]["score"] = r.get("score")
            else:
                merged[qno] = {
                    "type": "essay",
                    "qno": qno,
                    "score": r.get("score") or 0,
                    "rect": dict(r["rect"]),
                }
        elif r.get("type") == "choice_group":
            choice_groups.append(r)

    # 组装输出：先选择题组（按 qg_indexno 排序），再主观题（按 qno 排序）
    result = []
    for i, cg in enumerate(sorted(choice_groups, key=lambda x: x.get("qg_indexno") or 0)):
        cg.setdefault("id", f"CG{i+1:02d}")
        result.append(cg)
    for i, qno in enumerate(sorted(merged.keys())):
        m = merged[qno]
        m["id"] = f"Q{qno:02d}"
        result.append(m)

    logger.info("auto_detect: %s raw=%d merged=%d (size=%dx%d)",
                img_path.name, len(clean), len(result), w, h)
    return {"regions": result, "width": w, "height": h, "raw": content[:2000]}
