"""答题卡 PDF 渲染器 — reportlab 实现（TQL 像素级复刻 v2）。"""
from __future__ import annotations
import base64
import io
import re
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

from .layout import mm_to_pt, REFERENCE_DPI

logger = logging.getLogger(__name__)

TQL_STYLE = {
    # 裁切线
    "cutting_line_dash": [10, 4],       # TQL: 粗长线段 + 短间隔
    "cutting_line_y_mm": 3,
    "cutting_line_sq_mm": 4.5,          # TQL: 端点方块 ~4.5mm
    "cutting_line_width_pt": 3.0,       # TQL: 粗虚线 ~3pt
    # 标题区
    "title_font_size": 24,
    "subtitle_font_size": 28,
    "name_line_width_mm": 50,
    "exam_id_boxes": 8,
    "exam_id_box_size_mm": 5,
    # 条形码区
    "barcode_w_mm": 55,
    "barcode_h_mm": 25,
    "barcode_dash": [3, 2],
    # 选择题
    "bracket_w_mm": 6,
    "bracket_h_mm": 5,
    "bracket_row_gap_mm": 5.5,
    "bracket_col_gap_mm": 7,
    # 主观题
    "border_width_pt": 1.0,             # TQL: 细黑框 ~1pt（非粗框）
    "writing_line_gap_mm": 7,
    "writing_line_color": (0.78, 0.78, 0.78),  # TQL: 极淡灰书写线（参考图几乎不可见）
    "writing_line_width_pt": 0.15,      # TQL: 极细线 ~0.15pt
    # 栏头/栏底警告
    "warning_font_size": 7,
    "warning_text": "请在各题对应答题区域内作答，超出矩形边框限定区域的答案无效",
}

# Backward compat alias
DEFAULT_STYLE = TQL_STYLE


def _merge_style(custom: dict | None) -> dict:
    """合并自定义样式到默认样式。"""
    merged = dict(TQL_STYLE)
    if custom:
        merged.update(custom)
    return merged

# ── 双字体系统 ──────────────────────────────────────
# SimHei (黑体) → 标题、节标题、题号
# SimSun (宋体) → 正文、注意事项、警告文字

_FONT_TITLE = "Helvetica-Bold"
_FONT_BODY = "Helvetica"
_FONT_REGISTERED = False


def _ensure_chinese_font():
    """注册 SimHei(黑体) + SimSun(宋体) 双字体。"""
    global _FONT_TITLE, _FONT_BODY, _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    _FONT_REGISTERED = True

    # 标题字体：SimHei (黑体) — 粗壮笔画，用于标题和节标题
    title_candidates = [
        ("C:/Windows/Fonts/simhei.ttf", None),
        ("/mnt/c/Windows/Fonts/simhei.ttf", None),
        ("C:/Windows/Fonts/msyhbd.ttc", 0),
        ("/mnt/c/Windows/Fonts/msyhbd.ttc", 0),
        ("C:/Windows/Fonts/msyh.ttc", 0),
        ("/mnt/c/Windows/Fonts/msyh.ttc", 0),
        # Linux/Docker: Droid Sans Fallback（TrueType CJK，reportlab 兼容；
        # Noto CJK .ttc 是 CFF PostScript outlines 不被 reportlab 支持）
        ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", None),
    ]
    for fp, idx in title_candidates:
        try:
            kw = {"subfontIndex": idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont("SimHei", fp, **kw))
            _FONT_TITLE = "SimHei"
            logger.info("Registered title font (SimHei): %s", fp)
            break
        except Exception:
            continue

    # 正文字体：SimSun (宋体) — 规范印刷体，用于正文和注意事项
    body_candidates = [
        ("C:/Windows/Fonts/simsun.ttc", 0),
        ("/mnt/c/Windows/Fonts/simsun.ttc", 0),
        ("C:/Windows/Fonts/msyh.ttc", 0),
        ("/mnt/c/Windows/Fonts/msyh.ttc", 0),
        # Linux/Docker: Droid Sans Fallback（TrueType CJK 兜底）
        ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", None),
    ]
    for fp, idx in body_candidates:
        try:
            kw = {"subfontIndex": idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont("SimSun", fp, **kw))
            _FONT_BODY = "SimSun"
            logger.info("Registered body font (SimSun): %s", fp)
            break
        except Exception:
            continue

    # 兜底：如果都没注册成功，尝试任意一个
    if _FONT_TITLE == "Helvetica-Bold" and _FONT_BODY == "Helvetica":
        for fp, idx in [
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("/mnt/c/Windows/Fonts/msyh.ttc", 0),
            ("C:/Windows/Fonts/simsun.ttc", 0),
            ("/mnt/c/Windows/Fonts/simsun.ttc", 0),
            ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", None),
        ]:
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", fp, subfontIndex=idx))
                _FONT_TITLE = "ChineseFont"
                _FONT_BODY = "ChineseFont"
                logger.info("Registered fallback font: %s (idx=%s)", fp, idx)
                break
            except Exception:
                continue


# ── 坐标精化 ──────────────────────────────────────

NOTICE_HEIGHT_MM = 30.0       # 注意事项框高度
ABSENT_MARK_HEIGHT_MM = 5.0   # 缺考标记行高度
SECTION_BAR_HEIGHT_MM = 5.5   # 分节标题条高度
COMPONENT_GAP_MM = 1.0        # 组件间距


def _calc_anchor_bottom_mm(skeleton: dict, px_to_mm) -> float:
    """计算顶部锚点底部 y（mm）。"""
    anchors = skeleton.get("anchors", [])
    img_h = skeleton.get("image_height", 2339)
    top_anchors = [a for a in anchors if a["rect"]["y1"] < img_h / 2]
    if not top_anchors:
        return px_to_mm(100)
    return px_to_mm(max(a["rect"]["y2"] for a in top_anchors)) + 2


def _calc_header_height_mm(anchor_bottom_mm: float, style: dict,
                           skeleton: dict) -> float:
    """计算 header 区域（标题+OMR+个人信息）的底部 y（mm）。

    逻辑与 _draw_tql_header 完全一致，但不画图。
    """
    y = anchor_bottom_mm + 2

    # 标题行
    y += 12  # 考试名称行高

    # 副标题行
    y += 12  # "XX 答题卡"行高

    # 左侧 OMR 填涂区
    n_digits = skeleton.get("exam_number_digits", 8)
    if n_digits <= 0:
        n_digits = 8
    cell_h = 3.8
    header_h = 4.5
    grid_total_h = header_h + 10 * cell_h + 2
    grid_start = y + 6  # 标题下方
    bubble_area_bottom = grid_start + grid_total_h

    # 右侧个人信息
    field_gap = 7.0
    info_bottom = y + field_gap * 2 + 8

    return max(bubble_area_bottom, info_bottom) + 2


def _calc_choice_group_height_mm(group: dict, style: dict) -> float:
    """计算单个选择题组的高度（mm）。

    纵向布局：标题行 + 题号行 + options 行(ABCD) × 行间距。
    """
    options = group.get("options", 4)
    row_gap = style.get("bracket_row_gap_mm", 5.5)
    title_h = 6.0   # 标题行
    header_h = 5.0   # 题号行

    return title_h + header_h + options * row_gap + 2


def _calc_fillin_height_mm(skeleton: dict, style: dict) -> float:
    """计算填空题组的高度（mm）。"""
    group = skeleton.get("fillin_group")
    if not group:
        return 0
    count = group.get("count", 0)
    rows = (count + 1) // 2
    fillin_header = 7.0
    row_h = 12.0
    return fillin_header + rows * row_h + 2


def finalize_skeleton(skeleton: dict, style: dict | None = None) -> dict:
    """链式计算 header 区域所有组件的精确 y 坐标，回写到 skeleton。

    Returns:
        dict: renderer 内部需要的中间值 {header_bottom_mm, notice_bottom_mm, absent_bottom_mm}
    """
    if not skeleton.get("_needs_finalize"):
        # DB 导入的 .tpl skeleton 已有准确坐标，跳过
        return {}

    s = _merge_style(style)
    source_dpi = skeleton.get("source_dpi", 200)

    def px_to_mm(px: float) -> float:
        return px * 25.4 / source_dpi

    def mm_to_px(val_mm: float) -> int:
        return round(val_mm * source_dpi / 25.4)

    # 链式计算（mm）
    anchor_bottom = _calc_anchor_bottom_mm(skeleton, px_to_mm)
    header_bottom = _calc_header_height_mm(anchor_bottom, s, skeleton)
    notice_bottom = header_bottom + COMPONENT_GAP_MM + NOTICE_HEIGHT_MM + COMPONENT_GAP_MM
    absent_bottom = notice_bottom + COMPONENT_GAP_MM + ABSENT_MARK_HEIGHT_MM

    y_cursor = absent_bottom + COMPONENT_GAP_MM

    # "第 I 卷 选择题"
    section1_y = 0
    if skeleton.get("has_objectives"):
        section1_y = y_cursor
        y_cursor += SECTION_BAR_HEIGHT_MM

        # 回写 objective_groups rect
        for group in skeleton.get("objective_groups", []):
            group_h = _calc_choice_group_height_mm(group, s)
            group["rect"]["y1"] = mm_to_px(y_cursor)
            group["rect"]["y2"] = mm_to_px(y_cursor + group_h)
            y_cursor += group_h + COMPONENT_GAP_MM

    # "第 II 卷 非选择题"
    section2_y = 0
    if skeleton.get("has_fillins") or skeleton.get("has_essays"):
        section2_y = y_cursor
        y_cursor += SECTION_BAR_HEIGHT_MM

    # "二、填空题" — 保持现有契约：fillin_group.rect 包含标题区
    # _draw_fillin_group 假设 start_y = y1_mm + 7.0 + 2（标题在 group 内部）
    fillin_title_y = 0
    if skeleton.get("has_fillins"):
        fillin_title_y = y_cursor
        fillin_h = _calc_fillin_height_mm(skeleton, s)
        if skeleton.get("fillin_group"):
            skeleton["fillin_group"]["rect"]["y1"] = mm_to_px(y_cursor)
            skeleton["fillin_group"]["rect"]["y2"] = mm_to_px(y_cursor + fillin_h)
        y_cursor += fillin_h + COMPONENT_GAP_MM

    # "三、解答题"
    essay_title_y = 0
    if skeleton.get("has_essays"):
        essay_title_y = y_cursor
        y_cursor += SECTION_BAR_HEIGHT_MM

    # 回写 section_headers（像素）
    skeleton["section_headers"] = {
        "section1_y": mm_to_px(section1_y) if section1_y else 0,
        "section2_y": mm_to_px(section2_y) if section2_y else 0,
        "fillin_title_y": mm_to_px(fillin_title_y) if fillin_title_y else 0,
        "essay_title_y": mm_to_px(essay_title_y) if essay_title_y else 0,
    }

    # 回写 columns[0].y1（page=0, col_1）
    essay_start_px = mm_to_px(y_cursor)
    for col in skeleton.get("columns", []):
        if col.get("page", 0) == 0 and col["id"] == "col_1":
            col["y1"] = essay_start_px

    # 清除标记
    skeleton.pop("_needs_finalize", None)

    return {
        "header_bottom_mm": header_bottom,
        "notice_bottom_mm": notice_bottom,
        "absent_bottom_mm": absent_bottom,
    }


def render_card_v2(
    skeleton: dict,
    layout: dict,
    exam_name: str,
    subject_name: str,
    *,
    style: dict | None = None,
) -> bytes:
    """v2 渲染器：根据骨架 + 布局 JSON 生成答题卡 PDF。

    统一走 _render_full_page() 代码生成路径。
    旧 .tpl 背景图路径仅在 tpl_images 存在时保留兼容。
    """
    _ensure_chinese_font()
    s = _merge_style(style)

    source_dpi = skeleton.get("source_dpi", 200)
    img_w = skeleton["image_width"]
    img_h = skeleton["image_height"]

    def px_to_mm(px: float) -> float:
        return px * 25.4 / source_dpi

    page_w_mm = px_to_mm(img_w)
    page_h_mm = px_to_mm(img_h)
    page_w_pt = mm_to_pt(page_w_mm)
    page_h_pt = mm_to_pt(page_h_mm)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w_pt, page_h_pt))

    def y_flip(y_mm: float) -> float:
        return page_h_pt - y_mm * mm

    has_tpl = bool(skeleton.get("subjective_slots"))
    tpl_images = skeleton.get("tpl_images", {})
    is_a4_half = skeleton.get("page_width", 0) <= 2000

    if has_tpl and tpl_images.get(0):
        # 旧路径：有 .tpl 背景图，贴图
        if is_a4_half:
            _render_tpl_a4_pair(c, tpl_images, page_w_pt, page_h_pt)
        else:
            _draw_bg_image(c, tpl_images[0], page_w_pt, page_h_pt)
    else:
        # 统一代码生成路径
        _render_full_page(c, skeleton, layout, exam_name, subject_name,
                          source_dpi, page_w_mm, page_h_mm, page_w_pt, page_h_pt,
                          px_to_mm, y_flip, s)

    # Page 1（背面）
    if has_tpl and not is_a4_half and tpl_images.get(1):
        c.showPage()
        c.setPageSize((page_w_pt, page_h_pt))
        _draw_bg_image(c, tpl_images[1], page_w_pt, page_h_pt)
    else:
        page1_slots = [s_ for s_ in layout.get("slots", []) if s_.get("inpage", 0) == 1]
        if page1_slots:
            c.showPage()
            c.setPageSize((page_w_pt, page_h_pt))
            # 背面：只用 page=1 的列
            back_cols = [c_ for c_ in skeleton.get("columns", []) if c_.get("page", 0) == 1]
            _draw_corner_marks_from_skeleton(c, skeleton, px_to_mm, y_flip)
            _draw_column_dividers(c, back_cols, px_to_mm, page_h_mm, y_flip)
            _draw_column_warnings(c, back_cols, px_to_mm, page_h_mm, y_flip, s,
                                  skip_header=True)
            for slot in page1_slots:
                _draw_slot_regions(c, slot, px_to_mm, y_flip, s)

    c.save()
    return buf.getvalue()


# ── 统一代码生成路径 ──────────────────────────────────────

def _render_full_page(c, skeleton, layout, exam_name, subject_name,
                      source_dpi, page_w_mm, page_h_mm, page_w_pt, page_h_pt,
                      px_to_mm, y_flip, style):
    """TQL 风格统一渲染路径。"""
    columns = [c_ for c_ in skeleton.get("columns", []) if c_.get("page", 0) == 0]

    # 1. 裁切虚线
    _draw_cutting_line(c, page_w_mm, style, y_flip)

    # 2. 定位锚点
    _draw_corner_marks_from_skeleton(c, skeleton, px_to_mm, y_flip)

    # 3. 分栏线
    _draw_column_dividers(c, columns, px_to_mm, page_h_mm, y_flip)

    # 4. 标题区
    finalize_hints = skeleton.get("_finalize_hints")
    if finalize_hints is None:
        finalize_hints = finalize_skeleton(skeleton, style)
        if finalize_hints:
            skeleton["_finalize_hints"] = finalize_hints

    header_bottom = _draw_tql_header(c, skeleton, exam_name, subject_name, px_to_mm, y_flip, style)

    # 5. 注意事项 — 紧贴表头下方
    if finalize_hints:
        notice_y_start = finalize_hints["header_bottom_mm"]
    elif header_bottom is not None:
        notice_y_start = header_bottom
    else:
        notice_y_start = None
    notice_bottom = _draw_tql_notice(c, skeleton, px_to_mm, y_flip, style,
                                     y_start_mm=notice_y_start)

    # 6. 缺考标记 — 紧贴注意事项下方
    if finalize_hints:
        absent_y_start = finalize_hints["notice_bottom_mm"]
    elif notice_bottom is not None:
        absent_y_start = notice_bottom
    else:
        absent_y_start = None
    _draw_absent_mark(c, skeleton, px_to_mm, y_flip, style,
                      y_start_mm=absent_y_start)

    # 7. 分节标题栏
    _draw_section_headers(c, skeleton, px_to_mm, y_flip, style)

    # 8. 选择题（合并同类 group，共享标题）
    _draw_all_choice_groups(c, skeleton, px_to_mm, y_flip, style)

    # 9. 填空题组（紧凑渲染）
    _draw_fillin_group(c, skeleton, px_to_mm, y_flip, style)

    # 10. 栏头/栏底警告
    _draw_column_warnings(c, columns, px_to_mm, page_h_mm, y_flip, style)

    # 11. 解答题区域
    page0_slots = [s_ for s_ in layout.get("slots", []) if s_.get("inpage", 0) == 0]
    for slot in page0_slots:
        _draw_slot_regions(c, slot, px_to_mm, y_flip, style)

    # 10. "请勿在此区域答题" 水印（TQL 签名元素）
    _draw_no_answer_watermark(c, skeleton, layout, px_to_mm, y_flip, page_h_mm)


def _draw_no_answer_watermark(c, skeleton, layout, px_to_mm, y_flip, page_h_mm):
    """在任意栏的空白区域绘制竖排"请勿在此区域答题"水印（TQL 风格）。"""
    columns = skeleton.get("columns", [])
    if not columns:
        return

    page0_slots = [s_ for s_ in layout.get("slots", []) if s_.get("inpage", 0) == 0]

    for col in columns:
        col_x1_mm = px_to_mm(col["x1"])
        col_x2_mm = px_to_mm(col["x2"])
        col_center_mm = (col_x1_mm + col_x2_mm) / 2
        col_bottom_mm = px_to_mm(col["y2"])

        # 找到该栏最后一个主观题底部
        last_y2_mm = 0
        for slot in page0_slots:
            for sr in slot.get("sub_regions", []):
                sr_x_mm = px_to_mm(sr["rect"]["x1"])
                if col_x1_mm - 2 <= sr_x_mm <= col_x2_mm + 2:
                    sr_y2_mm = px_to_mm(sr["rect"]["y2"])
                    last_y2_mm = max(last_y2_mm, sr_y2_mm)

        # 该栏没有任何题目 → 从栏顶开始画水印
        if last_y2_mm == 0:
            last_y2_mm = px_to_mm(col["y1"])

        available = col_bottom_mm - last_y2_mm
        if available > 40:
            text = "请勿在此区域答题"
            # 动态计算字号：让文字尽量填满可用空间（TQL 风格大字水印）
            char_count = len(text)
            max_char_h = (available - 20) / char_count  # 上下各留 10mm
            font_size = min(max_char_h * 2.2, 72)  # 上限 72pt
            font_size = max(font_size, 20)  # 下限 20pt
            char_spacing = max_char_h

            watermark_y = last_y2_mm + (available - char_count * char_spacing) / 2
            c.saveState()
            c.setFillColorRGB(0.75, 0.75, 0.75)
            c.setFont(_FONT_TITLE, font_size)
            for i, ch in enumerate(text):
                c.drawCentredString(col_center_mm * mm, y_flip(watermark_y + i * char_spacing), ch)
            c.restoreState()


def _draw_corner_marks_from_skeleton(c, skeleton, px_to_mm, y_flip):
    """从 skeleton.anchors 读取坐标绘制定位黑块（与导出 JSON 一致）。"""
    c.setFillColorRGB(0, 0, 0)
    for anchor in skeleton.get("anchors", []):
        rect = anchor["rect"]
        x_mm = px_to_mm(rect["x1"])
        y_mm = px_to_mm(rect["y1"])
        w_mm = px_to_mm(rect["x2"] - rect["x1"])
        h_mm = px_to_mm(rect["y2"] - rect["y1"])
        c.rect(x_mm * mm, y_flip(y_mm + h_mm), w_mm * mm, h_mm * mm, fill=1, stroke=0)


def _draw_cutting_line(c, page_w_mm, style, y_flip):
    """TQL 顶部裁切虚线 — ■── ── ──■ 样式，两端有黑色方块标记。"""
    y_mm = style.get("cutting_line_y_mm", 3)
    dash = style.get("cutting_line_dash", [10, 4])
    margin_mm = 5
    sq = style.get("cutting_line_sq_mm", 4.5)
    line_w = style.get("cutting_line_width_pt", 3.0)

    # 左端方块
    c.setFillColorRGB(0, 0, 0)
    c.rect(margin_mm * mm, y_flip(y_mm + sq / 2), sq * mm, sq * mm, fill=1, stroke=0)
    # 右端方块
    c.rect((page_w_mm - margin_mm - sq) * mm, y_flip(y_mm + sq / 2), sq * mm, sq * mm, fill=1, stroke=0)

    # 粗虚线（两端方块之间，TQL 风格：粗线段+短间隔）
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(line_w)
    c.setDash(dash[0], dash[1])
    line_start = margin_mm + sq + 1
    line_end = page_w_mm - margin_mm - sq - 1
    c.line(line_start * mm, y_flip(y_mm), line_end * mm, y_flip(y_mm))
    c.setDash()


# ── 标题区 ──────────────────────────────────────

def _draw_tql_header(c, skeleton, exam_name, subject_name, px_to_mm, y_flip, style):
    """标题区：考试名 + 科目答题卡 + 带边框的学生信息区（姓名/准考证号方格/条形码区）。

    参考图布局（固定，不随 A3/A4 变化）：
              2024年秋季高二检测卷
                数学答题卡
    ┌──────────────────────────────────────────┐
    │ 姓  名 __________     ┌贴条形码区──────┐ │
    │                       │(正面朝上,切勿  │ │
    │ 准考证号 □□□□□□□□□    │ 贴出虚线方框)  │ │
    │                       └────────────────┘ │
    └──────────────────────────────────────────┘
    """
    columns = skeleton.get("columns", [])
    anchors = skeleton.get("anchors", [])
    if not columns or not anchors:
        return

    col1 = min(columns, key=lambda c_: c_["x1"])
    x1_mm = px_to_mm(col1["x1"])
    x2_mm = px_to_mm(col1["x2"])
    col_w = x2_mm - x1_mm
    center_pt = (x1_mm + x2_mm) / 2 * mm

    top_anchors = [a for a in anchors if a["rect"]["y1"] < skeleton["image_height"] / 2]
    anchor_bottom_mm = px_to_mm(max((a["rect"]["y2"] for a in top_anchors), default=100)) + 2

    y = anchor_bottom_mm + 2

    # ── 考试名称（黑体，居中）──
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_FONT_TITLE, style.get("title_font_size", 16))
    c.drawCentredString(center_pt, y_flip(y + 5), exam_name)
    y += 8

    # ── "XX答题卡"（黑体大号，字间距加宽，居中）──
    c.setFont(_FONT_TITLE, style.get("subtitle_font_size", 20))
    spaced_name = " ".join(subject_name)
    c.drawCentredString(center_pt, y_flip(y + 6), f"{spaced_name} 答 题 卡")
    y += 10

    # ── 学生信息区（带外边框）──
    info_box_y = y
    info_box_h = 22.0  # mm
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.rect(x1_mm * mm, y_flip(info_box_y + info_box_h),
           col_w * mm, info_box_h * mm, fill=0, stroke=1)

    left_x = x1_mm + 3
    inner_y = info_box_y + 3

    # 姓名 + 横线
    c.setFont(_FONT_TITLE, 11)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(left_x * mm, y_flip(inner_y + 3.5), "姓\u3000名")
    ul_x = left_x + 16
    ul_end = x1_mm + col_w * 0.48
    c.setLineWidth(0.5)
    c.line(ul_x * mm, y_flip(inner_y + 4.5), ul_end * mm, y_flip(inner_y + 4.5))

    # 准考证号 + 小方格
    row2_y = inner_y + 11
    c.setFont(_FONT_TITLE, 11)
    c.drawString(left_x * mm, y_flip(row2_y + 3.5), "准考证号")
    n_digits = skeleton.get("exam_number_digits", 9)
    if n_digits <= 0:
        n_digits = 9
    box_size = 4.0  # mm
    box_gap = 0.8   # mm
    box_start_x = ul_x
    c.setLineWidth(0.4)
    for i in range(n_digits):
        bx = box_start_x + i * (box_size + box_gap)
        c.rect(bx * mm, y_flip(row2_y + 4.5),
               box_size * mm, box_size * mm, fill=0, stroke=1)

    # 右侧：贴条形码区（虚线矩形）
    barcode_x = x1_mm + col_w * 0.55
    barcode_w = col_w * 0.40
    barcode_h = info_box_h - 4
    barcode_y = info_box_y + 2

    c.setLineWidth(0.6)
    c.setDash(3, 2)
    c.rect(barcode_x * mm, y_flip(barcode_y + barcode_h),
           barcode_w * mm, barcode_h * mm, fill=0, stroke=1)
    c.setDash()

    bc_center = barcode_x + barcode_w / 2
    c.setFont(_FONT_TITLE, 10)
    c.drawCentredString(bc_center * mm, y_flip(barcode_y + 5), "贴条形码区")
    c.setFont(_FONT_BODY, 7)
    c.drawCentredString(bc_center * mm, y_flip(barcode_y + 10),
                        "（正面朝上，切勿贴出虚线方框）")

    header_bottom = info_box_y + info_box_h + 1
    return header_bottom


# ── 缺考标记（TQL 标准：注意事项下方、选择题上方）──────────────────────

def _draw_absent_mark(c, skeleton, px_to_mm, y_flip, style, *, y_start_mm=None):
    """TQL 缺考标记行：□ ←── 此方框为缺考考生标记... ■"""
    columns = skeleton.get("columns", [])
    anchors = skeleton.get("anchors", [])
    if not columns or not anchors:
        return

    col1 = min(columns, key=lambda c_: c_["x1"])
    x1_mm = px_to_mm(col1["x1"])
    x2_mm = px_to_mm(col1["x2"])

    if y_start_mm is not None:
        box_y = y_start_mm
    else:
        top_anchors = [a for a in anchors if a["rect"]["y1"] < skeleton["image_height"] / 2]
        anchor_bottom_mm = px_to_mm(max((a["rect"]["y2"] for a in top_anchors), default=100)) + 2
        box_y = anchor_bottom_mm + 48 + 30 + 1

    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    # 左侧空心方框
    c.rect((x1_mm + 2) * mm, y_flip(box_y + 3.5), 3.5 * mm, 3.5 * mm, fill=0, stroke=1)
    # 箭头线 + 说明文字
    arrow_x = x1_mm + 6.5
    c.setLineWidth(0.4)
    c.line(arrow_x * mm, y_flip(box_y + 1.5), (arrow_x + 4) * mm, y_flip(box_y + 1.5))
    c.setFont(_FONT_BODY, 7)
    c.drawString((arrow_x + 5) * mm, y_flip(box_y + 2.5),
                 "此方框为缺考考生标记，由监考员用2B铅笔填涂。")
    # 右侧实心方块
    c.setFillColorRGB(0, 0, 0)
    c.rect((x2_mm - 5) * mm, y_flip(box_y + 3.5), 3.5 * mm, 3.5 * mm, fill=1, stroke=0)


# ── 注意事项（TQL 竖排标签风格）──────────────────────────────────────

def _draw_tql_notice(c, skeleton, px_to_mm, y_flip, style, *, y_start_mm=None):
    """TQL 注意事项框：左侧竖排"注意事项"标签 + 5条编号列表 + 右侧填涂示例。

    TQL 原版布局：
    ┌──┬─────────────────────────────────────┐
    │注│1.答题前，考生先将...           正 确 │
    │意│  名、准考证号...               填 涂 │
    │事│2.选择题部分...                 示 例 │
    │项│3.非选择题...                   ■  □  │
    │  │4.在草稿纸...                         │
    │  │5.请勿折叠...                         │
    └──┴─────────────────────────────────────┘
    """
    columns = skeleton.get("columns", [])
    anchors = skeleton.get("anchors", [])
    if not columns or not anchors:
        return

    col1 = min(columns, key=lambda c_: c_["x1"])
    x1_mm = px_to_mm(col1["x1"])
    x2_mm = px_to_mm(col1["x2"])
    col_w = x2_mm - x1_mm

    # 从 header 底部开始，而非硬编码偏移
    if y_start_mm is not None:
        notice_y = y_start_mm
    else:
        top_anchors = [a for a in anchors if a["rect"]["y1"] < skeleton["image_height"] / 2]
        anchor_bottom_mm = px_to_mm(max((a["rect"]["y2"] for a in top_anchors), default=100)) + 2
        notice_y = anchor_bottom_mm + 48

    notice_h = 30.0  # mm（TQL 实测约 30mm）
    label_col_w = 7.0  # 竖排标签列宽 mm

    # ── 外框 ──
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.6)
    c.rect(x1_mm * mm, y_flip(notice_y + notice_h), col_w * mm, notice_h * mm, fill=0, stroke=1)

    # ── 标签列分隔竖线 ──
    sep_x = x1_mm + label_col_w
    c.line(sep_x * mm, y_flip(notice_y), sep_x * mm, y_flip(notice_y + notice_h))

    # ── "注意事项" 竖排文字 ──
    label_center_x = (x1_mm + sep_x) / 2
    chars = "注意事项"
    char_start_y = notice_y + 4.5
    char_gap = 5.5
    c.setFont(_FONT_TITLE, 9)
    c.setFillColorRGB(0, 0, 0)
    for i, ch in enumerate(chars):
        c.drawCentredString(label_center_x * mm, y_flip(char_start_y + i * char_gap), ch)

    # ── 5 条注意事项文本 ──
    text_x = sep_x + 1.5
    c.setFont(_FONT_BODY, 7)
    notices = [
        "1.答题前，考生先将自己的姓名、准考证号填写清楚，并认真核对条形码上的姓",
        "  名、准考证号和科目；",
        "2.选择题部分请用2B铅笔填涂方格，修改时用橡皮擦干净，不要留痕迹；",
        "3.非选择题部分请用0.5毫米黑色墨水签字笔书写，字体工整、笔迹清楚；",
        "4.在草稿纸、试题卷上答题无效；",
        "5.请勿折叠答题卡，保持字体工整、笔迹清晰、卡面清洁。",
    ]
    text_y = notice_y + 4.5
    for line in notices:
        c.drawString(text_x * mm, y_flip(text_y), line)
        text_y += 3.6

    # ── 填涂示例（右侧竖排 "正确/填涂/示例"）──
    example_x = x1_mm + col_w - 18
    example_y = notice_y + 4

    c.setFont(_FONT_BODY, 7.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(example_x * mm, y_flip(example_y), "正  确")
    c.drawString(example_x * mm, y_flip(example_y + 4), "填  涂")
    c.drawString(example_x * mm, y_flip(example_y + 8), "示  例")

    # 示例方块（实心=正确，空心=错误）
    block_x = example_x + 12
    block_size = 3.5  # mm
    # ■ 正确填涂
    c.setFillColorRGB(0, 0, 0)
    c.rect(block_x * mm, y_flip(example_y + 4), block_size * mm, block_size * mm, fill=1, stroke=1)
    # □ 错误
    c.rect((block_x + 5) * mm, y_flip(example_y + 4), block_size * mm, block_size * mm, fill=0, stroke=1)

    return notice_y + notice_h + 1  # 返回底部 y


# ── 分节标题 + 填空题 ──────────────────────────────────────

def _draw_section_headers(c, skeleton, px_to_mm, y_flip, style):
    """TQL 分节标题栏："第 I 卷 选择题"、"第 II 卷 非选择题"、填空/解答题标题。"""
    headers = skeleton.get("section_headers", {})
    columns = skeleton.get("columns", [])
    if not columns:
        return

    col1 = min(columns, key=lambda c_: c_["x1"])
    x1_mm = px_to_mm(col1["x1"])
    x2_mm = px_to_mm(col1["x2"])
    col_w = x2_mm - x1_mm
    center_x = (x1_mm + x2_mm) / 2

    def _draw_bar(y_px, text, is_major=True):
        """画分节标题条（黑底白字 或 带框标题）。"""
        y_mm = px_to_mm(y_px)
        bar_h = 5.5  # mm
        if is_major:
            # 黑底白字条
            c.setFillColorRGB(0, 0, 0)
            c.rect(x1_mm * mm, y_flip(y_mm + bar_h), col_w * mm, bar_h * mm, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont(_FONT_TITLE, 10)
            c.drawCentredString(center_x * mm, y_flip(y_mm + bar_h - 1.5), text)
        else:
            # 细框标题（填空题/解答题标题）
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            c.rect(x1_mm * mm, y_flip(y_mm + bar_h), col_w * mm, bar_h * mm, fill=0, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont(_FONT_TITLE, 9)
            c.drawString((x1_mm + 2) * mm, y_flip(y_mm + bar_h - 1.5), text)

    # "第 Ⅰ 卷  选择题"
    if skeleton.get("has_objectives") and headers.get("section1_y"):
        _draw_bar(headers["section1_y"], "第 Ⅰ 卷    选  择  题")

    # "第 Ⅱ 卷  非选择题"
    if (skeleton.get("has_fillins") or skeleton.get("has_essays")) and headers.get("section2_y"):
        _draw_bar(headers["section2_y"], "第 Ⅱ 卷    非 选 择 题")

    # "二、填空题（共N个小题，每小题X分，共Y分）"
    if skeleton.get("has_fillins") and headers.get("fillin_title_y"):
        n = skeleton.get("fillin_count", 0)
        fillin_group = skeleton.get("fillin_group", {})
        qs = fillin_group.get("questions", [])
        per_score = qs[0].get("score", 5) if qs else 5
        total = n * per_score
        title = f"二、填空题（共{n}个小题，每小题{int(per_score)}分，共{int(total)}分）"
        _draw_bar(headers["fillin_title_y"], title, is_major=False)

    # "三、解答题（共N个小题，共Y分）"
    if skeleton.get("has_essays") and headers.get("essay_title_y"):
        n = skeleton.get("essay_count", 0)
        total_score = skeleton.get("essay_total_score", 0)
        if total_score > 0:
            _draw_bar(headers["essay_title_y"],
                      f"三、解答题（共{n}个小题，共{int(total_score)}分）", is_major=False)
        else:
            _draw_bar(headers["essay_title_y"], f"三、解答题（共{n}个小题）", is_major=False)


def _draw_fillin_group(c, skeleton, px_to_mm, y_flip, style):
    """TQL 填空题组渲染：2题一行，下划线格式。"""
    group = skeleton.get("fillin_group")
    if not group:
        return

    rect = group["rect"]
    x1_mm = px_to_mm(rect["x1"])
    x2_mm = px_to_mm(rect["x2"])
    y1_mm = px_to_mm(rect["y1"])
    y2_mm = px_to_mm(rect["y2"])
    col_w = x2_mm - x1_mm

    # 外框
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(style.get("border_width_pt", 1.0))
    c.rect(x1_mm * mm, y_flip(y2_mm), col_w * mm, (y2_mm - y1_mm) * mm, fill=0)

    questions = group.get("questions", [])
    row_h = 12.0  # mm per row
    start_y = y1_mm + 7.0 + 2  # after title bar + padding
    half_w = col_w / 2

    for i, q in enumerate(questions):
        row = i // 2
        col = i % 2
        qno = q["number"]

        qx = x1_mm + col * half_w + 3
        qy = start_y + row * row_h

        # 题号
        c.setFillColorRGB(0, 0, 0)
        c.setFont(_FONT_TITLE, 10)
        c.drawString(qx * mm, y_flip(qy + 4), f"{qno}.")

        # 下划线
        line_start = qx + 10
        line_end = x1_mm + (col + 1) * half_w - 5
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)
        c.line(line_start * mm, y_flip(qy + 5), line_end * mm, y_flip(qy + 5))


# ── 选择题 ──────────────────────────────────────

def _draw_all_choice_groups(c, skeleton, px_to_mm, y_flip, style):
    """合并所有选择题组，从 skeleton objective_groups rect 读取位置绘制。"""
    groups = skeleton.get("objective_groups", [])
    if not groups:
        return

    bracket_w = style.get("bracket_w_mm", 5.5)
    bracket_h = style.get("bracket_h_mm", 4.5)
    row_gap = style.get("bracket_row_gap_mm", 5.5)
    col_gap = style.get("bracket_col_gap_mm", 6.5)
    label_w = 8.0
    mark_size = 2.0    # 参考图 OMR 定位块较小
    title_h = 6.0

    sorted_groups = sorted(groups, key=lambda g: g["rect"]["y1"])
    last_y2_mm = 0  # 跟踪最后一个组的底部

    for gi, group in enumerate(sorted_groups):
        rect = group["rect"]
        x1_mm = px_to_mm(rect["x1"])
        x2_mm = px_to_mm(rect["x2"])
        cur_y = px_to_mm(rect["y1"])
        group_bottom = px_to_mm(rect["y2"])
        col_w = x2_mm - x1_mm

        is_multi = group.get("multi_select", False)
        symbols = group.get("symbols", "A,B,C,D").split(",")

        # 构建行数据
        all_rows = []
        for ri in range(group["count"]):
            all_rows.append({
                "qno": group.get("start_no", 1) + ri,
                "options": group["options"],
                "symbols": symbols,
            })

        # 标题
        title = "不定项选择题（请用2B铅笔填涂）" if is_multi else "选择题（请用2B铅笔填涂）"
        c.setFont(_FONT_TITLE, 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString((x1_mm + col_w / 2) * mm, y_flip(cur_y + 4), title)

        # 绘制选项 — 纵向排列（题号横排在顶部，ABCD 纵向排列）
        _draw_column_major_grid(c, all_rows, x1_mm, x2_mm, cur_y + title_h,
                                bracket_w, bracket_h, y_flip, style,
                                mark_size=mark_size)

        # 外框（使用 skeleton rect 精确边界）
        block_h = group_bottom - cur_y
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.6)
        c.rect(x1_mm * mm, y_flip(group_bottom), col_w * mm, block_h * mm,
               fill=0, stroke=1)

        last_y2_mm = group_bottom


def _draw_column_major_grid(c, rows, x1_mm, x2_mm, y_start,
                            bracket_w, bracket_h, y_flip, style,
                            mark_size=3.0):
    """TQL 列优先选择题网格：题号横排在顶部，ABCD 纵列。

    用于数学等选择题较多（>7题）的科目，匹配 TQL 纵向排列样式。
    返回绘制区域的高度（mm）。
    """
    if not rows:
        return 0

    options = rows[0]["options"]
    symbols = rows[0]["symbols"]
    col_count = len(rows)
    row_gap = 5.5  # ABCD 行间距
    col_gap_mm = max(4.0, (x2_mm - x1_mm - 8) / col_count)  # 动态列宽

    header_h = 5.0   # 题号行高度
    grid_start_y = y_start + header_h

    # 题号行（居中在每列上方）
    c.setFont(_FONT_TITLE, 7.5)
    c.setFillColorRGB(0, 0, 0)
    for ci, row in enumerate(rows):
        cx = x1_mm + 4 + ci * col_gap_mm + col_gap_mm / 2
        c.drawCentredString(cx * mm, y_flip(y_start + 3.5), str(row["qno"]))

    # ABCD 行（每行 = 一个选项字母，每列 = 一道题）
    for oi in range(options):
        sym = symbols[oi] if oi < len(symbols) else chr(65 + oi)
        oy = grid_start_y + oi * row_gap + row_gap * 0.5

        # 左侧 OMR 定位黑块
        c.setFillColorRGB(0, 0, 0)
        c.rect((x1_mm + 1) * mm, y_flip(oy + mark_size / 2),
               mark_size * mm, mark_size * mm, fill=1, stroke=0)

        # 每列画一个方括号
        for ci, row in enumerate(rows):
            bx = x1_mm + 4 + ci * col_gap_mm + (col_gap_mm - bracket_w) / 2
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.6)
            c.rect(bx * mm, y_flip(oy + bracket_h / 2),
                   bracket_w * mm, bracket_h * mm, fill=0, stroke=1)
            c.setFont(_FONT_TITLE, 8)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString((bx + bracket_w / 2) * mm,
                                y_flip(oy) - 1, sym)

        # 右侧 OMR 定位黑块
        c.setFillColorRGB(0, 0, 0)
        c.rect((x2_mm - mark_size - 1) * mm, y_flip(oy + mark_size / 2),
               mark_size * mm, mark_size * mm, fill=1, stroke=0)

    total_h = header_h + options * row_gap + 2
    return total_h


def _draw_bracket_rows(c, rows, x_mm, y_start, bracket_w, bracket_h,
                       row_gap, col_gap, label_w, y_flip, style,
                       mark_size=0, right_mark_x=0):
    """绘制方括号选择题行列表，含 OMR 定位黑块。"""
    for ri, row in enumerate(rows):
        qy = y_start + ri * row_gap + row_gap * 0.5
        qno = row["qno"]
        cols = row["options"]
        symbols = row["symbols"]

        # 左侧 OMR 定位黑块
        if mark_size > 0:
            c.setFillColorRGB(0, 0, 0)
            c.rect((x_mm + 1) * mm, y_flip(qy + mark_size / 2),
                   mark_size * mm, mark_size * mm, fill=1, stroke=0)

        # 题号（黑体）
        c.setFillColorRGB(0, 0, 0)
        c.setFont(_FONT_TITLE, 8)
        c.drawRightString((x_mm + label_w - 0.5) * mm, y_flip(qy) - 2, str(qno))

        # 括号选项 (A) (B) (C) (D) — 参考图使用圆括号文本样式
        for ci in range(cols):
            sym = symbols[ci] if ci < len(symbols) else chr(65 + ci)
            bx = x_mm + label_w + ci * col_gap
            c.setFillColorRGB(0, 0, 0)
            c.setFont(_FONT_BODY, 9)
            c.drawCentredString((bx + bracket_w / 2) * mm,
                                y_flip(qy) - 1.5, f"[{sym}]")

        # 右侧 OMR 定位黑块
        if right_mark_x > 0:
            c.setFillColorRGB(0, 0, 0)
            c.rect((right_mark_x - mark_size - 1) * mm, y_flip(qy + mark_size / 2),
                   mark_size * mm, mark_size * mm, fill=1, stroke=0)


# ── 栏头/栏底警告 ──────────────────────────────────────

def _draw_column_warnings(c, columns, px_to_mm, page_h_mm, y_flip, style,
                          *, skip_header=False):
    """TQL 栏头/栏底警告文字 + 底部黑方块。"""
    warning = style.get("warning_text",
                        "请在各题目的答题区域内作答，超出黑色矩形边框限定区域的答案无效")
    font_size = style.get("warning_font_size", 7)

    sorted_cols = sorted(columns, key=lambda c_: c_["x1"])

    for ci, col in enumerate(sorted_cols):
        x1_mm = px_to_mm(col["x1"])
        x2_mm = px_to_mm(col["x2"])
        col_center = (x1_mm + x2_mm) / 2 * mm

        # 栏头警告（跳过第 1 栏；背面页跳过全部栏头）
        if ci > 0 and not skip_header:
            header_y_mm = px_to_mm(col["y1"]) - 5
            c.setFont(_FONT_BODY, font_size)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(col_center, y_flip(header_y_mm), warning)

        # 栏底警告
        footer_y_mm = page_h_mm - 8
        c.setFont(_FONT_BODY, font_size)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(col_center, y_flip(footer_y_mm), warning)

        # 栏底左右黑方块标记
        mark_size = 3
        c.setFillColorRGB(0, 0, 0)
        c.rect(x1_mm * mm, y_flip(footer_y_mm + mark_size + 2),
               mark_size * mm, mark_size * mm, fill=1, stroke=0)
        c.rect((x2_mm - mark_size) * mm, y_flip(footer_y_mm + mark_size + 2),
               mark_size * mm, mark_size * mm, fill=1, stroke=0)


# ── 主观题区域 ──────────────────────────────────────

def _draw_subjective_region(c, sr, px_to_mm, y_flip, style, *,
                            is_first_sub=True, sub_label="", score=0):
    """TQL 主观题区域：粗黑边框 + 题号(本小题满分X分) + 解：(Ⅰ) + 书写横线。

    Args:
        is_first_sub: 是否为该题的第一个小题（画题号+分值）
        sub_label: 小题标签，如 "(Ⅰ)" "(Ⅱ)"
        score: 题目分值（用于显示 "本小题满分X分"）
    """
    rect = sr["rect"]
    x1_mm = px_to_mm(rect["x1"])
    y1_mm = px_to_mm(rect["y1"])
    x2_mm = px_to_mm(rect["x2"])
    y2_mm = px_to_mm(rect["y2"])
    w_mm = x2_mm - x1_mm
    h_mm = y2_mm - y1_mm

    if w_mm <= 0 or h_mm <= 0:
        return

    # 粗黑色矩形边框
    border_w = style.get("border_width_pt", 1.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(border_w)
    c.rect(x1_mm * mm, y_flip(y2_mm), w_mm * mm, h_mm * mm, fill=0)

    c.setFillColorRGB(0, 0, 0)
    content_top = y1_mm

    if is_first_sub:
        # 题号行：  "17.（本小题满分10分）"
        name = sr["name"]
        m = re.match(r'^(\d+)', name)
        qno = m.group(1) if m else name

        if score > 0:
            label = f"{qno}.（本小题满分 {int(score)} 分）"
        else:
            label = f"{qno}."
        c.setFont(_FONT_TITLE, 10)
        c.drawString((x1_mm + 2) * mm, y_flip(y1_mm + 5), label)
        content_top = y1_mm + 7

        # "解：" 或 "解：(Ⅰ)" 行
        if sub_label:
            c.setFont(_FONT_BODY, 9)
            c.drawString((x1_mm + 2) * mm, y_flip(content_top + 4), f"解：{sub_label}")
        else:
            c.setFont(_FONT_BODY, 9)
            c.drawString((x1_mm + 2) * mm, y_flip(content_top + 4), "解：")
        content_top += 6
    else:
        # 非首个小题：虚线分隔 + 小题标签
        # 顶部虚线分隔
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.setLineWidth(0.5)
        c.setDash(4, 3)
        c.line((x1_mm + 2) * mm, y_flip(y1_mm + 1), (x2_mm - 2) * mm, y_flip(y1_mm + 1))
        c.setDash()

        # 小题标签 "(Ⅱ)"
        if sub_label:
            c.setFont(_FONT_BODY, 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawString((x1_mm + 2) * mm, y_flip(y1_mm + 5), sub_label)
        content_top = y1_mm + 6

    # 密实书写横线
    line_gap = style.get("writing_line_gap_mm", 6)
    line_color = style.get("writing_line_color", (0, 0, 0))
    line_width = style.get("writing_line_width_pt", 0.3)

    c.setStrokeColorRGB(*line_color)
    c.setLineWidth(line_width)

    content_top += 2
    line_y = content_top
    while line_y < y2_mm - 2:
        c.line((x1_mm + 2) * mm, y_flip(line_y), (x2_mm - 2) * mm, y_flip(line_y))
        line_y += line_gap

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)


_ROMAN = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ", 5: "Ⅴ"}


def _draw_slot_regions(c, slot, px_to_mm, y_flip, style):
    """分发 slot 内所有 sub_region 的绘制，传递小题标签和分值。"""
    subs = slot.get("sub_regions", [])
    total_score = sum(sr.get("score", 0) for sr in subs)
    has_multi_subs = len(subs) > 1

    for i, sr in enumerate(subs):
        if sr.get("type") == "fill_blank":
            _draw_fillin_region(c, sr, px_to_mm, y_flip, style)
        else:
            is_first = (i == 0)
            sub_label = ""
            if has_multi_subs:
                sub_label = f"（{_ROMAN.get(i + 1, str(i + 1))}）"
            _draw_subjective_region(
                c, sr, px_to_mm, y_flip, style,
                is_first_sub=is_first,
                sub_label=sub_label,
                score=total_score if is_first else 0,
            )


def _draw_fillin_region(c, sr, px_to_mm, y_flip, style):
    """TQL 填空题区域：题号 + 下划线，无书写横线，无粗边框。"""
    rect = sr["rect"]
    x1_mm = px_to_mm(rect["x1"])
    y1_mm = px_to_mm(rect["y1"])
    x2_mm = px_to_mm(rect["x2"])
    y2_mm = px_to_mm(rect["y2"])
    w_mm = x2_mm - x1_mm
    h_mm = y2_mm - y1_mm

    if w_mm <= 0 or h_mm <= 0:
        return

    # 细边框（填空题边框比解答题细）
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.rect(x1_mm * mm, y_flip(y2_mm), w_mm * mm, h_mm * mm, fill=0)

    # 题号
    name = sr["name"]
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_FONT_TITLE, 10)
    c.drawString((x1_mm + 2) * mm, y_flip(y1_mm + 5), f"{name}.")

    # 下划线（题号右侧，宽度占满剩余空间）
    line_start = x1_mm + 12
    line_end = x2_mm - 3
    line_y = y1_mm + 5.5
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.line(line_start * mm, y_flip(line_y), line_end * mm, y_flip(line_y))


# ── .tpl 背景图渲染（兼容路径）──────────────────────────────────────

def _draw_bg_image(c, b64_data: str, page_w_pt: float, page_h_pt: float):
    """将 base64 PNG 作为全页背景绘制。"""
    img_bytes = base64.b64decode(b64_data)
    img_reader = ImageReader(io.BytesIO(img_bytes))
    c.drawImage(img_reader, 0, 0, width=page_w_pt, height=page_h_pt)


def _render_tpl_a4_pair(c, tpl_images: dict, page_w_pt: float, page_h_pt: float):
    """A4 半页模板：将 image[0](左半) 和 image[1](右半) 拼成 A3 正面。"""
    half_w = page_w_pt / 2
    if tpl_images.get(0):
        img_bytes = base64.b64decode(tpl_images[0])
        img_reader = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(img_reader, 0, 0, width=half_w, height=page_h_pt)
    if tpl_images.get(1):
        img_bytes = base64.b64decode(tpl_images[1])
        img_reader = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(img_reader, half_w, 0, width=half_w, height=page_h_pt)


def _draw_column_dividers(c, columns, px_to_mm, page_h_mm, y_flip):
    """画栏分隔竖线 + 底部中心定位黑块（TQL 标准）。"""
    if len(columns) < 2:
        return
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    sorted_cols = sorted(columns, key=lambda col: col["x1"])
    mark_size = 3  # mm
    for i in range(len(sorted_cols) - 1):
        mid_x_px = (sorted_cols[i]["x2"] + sorted_cols[i + 1]["x1"]) / 2
        mid_x_mm = px_to_mm(mid_x_px)
        top_mm = 5
        bottom_mm = page_h_mm - 5
        c.line(mid_x_mm * mm, y_flip(top_mm), mid_x_mm * mm, y_flip(bottom_mm))
        # 栏分隔线底部中心黑块（TQL 定位标记）
        c.setFillColorRGB(0, 0, 0)
        c.rect((mid_x_mm - mark_size / 2) * mm, y_flip(bottom_mm + mark_size),
               mark_size * mm, mark_size * mm, fill=1, stroke=0)
