"""条码贴纸 PDF 生成器。"""
from __future__ import annotations
import io
from pathlib import Path
import openpyxl
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
import logging

logger = logging.getLogger(__name__)


def parse_student_excel(
    file_path: Path | str,
    barcode_column: str = "准考证号",
    name_column: str = "姓名",
) -> list[dict]:
    """解析学生 Excel 文件。

    支持第 1 行为标题行（跳过），第 2 行为列头。

    Returns:
        [{"barcode": "53437193", "name": "张三"}, ...]
    """
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        raise ValueError("Excel 文件至少需要 2 行（列头 + 数据）")

    # 查找列头行（包含 barcode_column 的行）
    header_row_idx = None
    for i, row in enumerate(rows[:5]):
        str_row = [str(c) if c else "" for c in row]
        # 尝试 GBK 解码
        decoded_row = []
        for cell in str_row:
            try:
                decoded = cell.encode("latin1").decode("gbk")
            except (UnicodeDecodeError, UnicodeEncodeError):
                decoded = cell
            decoded_row.append(decoded)

        if barcode_column in decoded_row:
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError(f"未找到列 '{barcode_column}'，请检查 Excel 列头")

    headers = [str(c) if c else "" for c in rows[header_row_idx]]
    # GBK 解码 headers
    decoded_headers = []
    for h in headers:
        try:
            decoded_headers.append(h.encode("latin1").decode("gbk"))
        except (UnicodeDecodeError, UnicodeEncodeError):
            decoded_headers.append(h)

    try:
        bc_idx = decoded_headers.index(barcode_column)
    except ValueError:
        raise ValueError(f"未找到列 '{barcode_column}'")
    try:
        name_idx = decoded_headers.index(name_column)
    except ValueError:
        raise ValueError(f"未找到列 '{name_column}'")

    students = []
    for row in rows[header_row_idx + 1:]:
        if not row or not row[bc_idx]:
            continue
        students.append({
            "barcode": str(row[bc_idx]).strip(),
            "name": str(row[name_idx]).strip() if row[name_idx] else "",
        })

    return students


def render_barcode_pdf(
    students: list[dict],
    cols: int = 3,
    rows_per_page: int = 10,
    sticker_width_mm: float = 60.0,
    sticker_height_mm: float = 20.0,
) -> bytes:
    """生成条码贴纸 PDF。

    A4 纸，3列×10行 = 每页30个条码。
    """
    if not students:
        raise ValueError("学生列表为空")

    from . import renderer
    renderer._ensure_chinese_font()
    _FONT_NAME = renderer._FONT_BODY

    page_w = 210 * mm
    page_h = 297 * mm
    per_page = cols * rows_per_page

    total_w = cols * sticker_width_mm * mm + (cols - 1) * 5 * mm
    x_start = (page_w - total_w) / 2
    y_start = page_h - 20 * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    for idx, student in enumerate(students):
        if idx > 0 and idx % per_page == 0:
            c.showPage()

        pos_in_page = idx % per_page
        col = pos_in_page % cols
        row = pos_in_page // cols

        x = x_start + col * (sticker_width_mm + 5) * mm
        y = y_start - row * (sticker_height_mm + 3) * mm

        # 条码
        try:
            bc = code128.Code128(
                student["barcode"],
                barHeight=10 * mm,
                barWidth=0.33 * mm,
            )
            bc.drawOn(c, x, y - 10 * mm)
        except Exception as e:
            logger.warning("Failed to render barcode for %s: %s", student["barcode"], e)
            c.setFont(_FONT_NAME, 8)
            c.drawString(x, y - 8 * mm, f"[条码错误: {student['barcode']}]")

        # 文字
        c.setFont(_FONT_NAME, 7)
        label = f"{student['barcode']}  {student['name']}"
        c.drawString(x, y - 15 * mm, label)

    c.save()
    return buf.getvalue()
