"""填涂卡识别模块。

支持单选题、多选题、数字填涂、缺考标识的气泡识别。
算法：区域裁切 → OTSU 二值化 → 网格切分 → 填涂率统计 → 阈值判定。
"""
import dataclasses
import numpy as np
import cv2
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BubbleResult:
    """单个气泡的识别结果。"""
    row: int
    col: int
    label: str
    fill_ratio: float
    filled: bool


@dataclass
class GroupResult:
    """一个题组的识别结果。"""
    group_id: str = ""
    question_results: list = field(default_factory=list)


def _validate_region(region: dict) -> None:
    """校验 region 包含必需的坐标键、类型、非负、顺序。"""
    missing = [k for k in ("x1", "y1", "x2", "y2") if k not in region]
    if missing:
        raise ValueError(f"region missing keys: {missing}")
    for k in ("x1", "y1", "x2", "y2"):
        v = region[k]
        if not isinstance(v, (int, float)):
            raise TypeError(f"region[{k!r}] must be numeric, got {type(v).__name__}")
    if region["x1"] < 0 or region["y1"] < 0:
        raise ValueError("region coords must be non-negative")
    if region["x1"] >= region["x2"] or region["y1"] >= region["y2"]:
        raise ValueError("region must have x1<x2 and y1<y2")


def compute_fill_ratio(cell_gray: np.ndarray) -> float:
    """计算单个格子的填涂率（深色像素占比）。

    Args:
        cell_gray: 灰度图的单元格区域

    Returns:
        0.0-1.0 的填涂率
    """
    if cell_gray.size == 0:
        return 0.0
    _, binary = cv2.threshold(cell_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark_pixels = np.count_nonzero(binary)
    return dark_pixels / binary.size


def split_grid(
    gray: np.ndarray,
    rows: int,
    cols: int,
    padding: int = 2,
) -> list[list[np.ndarray]]:
    """将灰度图按网格切分为单元格。

    Args:
        gray: 灰度图（已裁切到目标区域）
        rows: 行数（题目数）
        cols: 列数（选项数）
        padding: 每个单元格的内边距（排除边框线）

    Returns:
        二维列表 cells[row][col]，每个元素是单元格灰度图
    """
    h, w = gray.shape[:2]
    cell_h = h // rows
    cell_w = w // cols

    cells = []
    for r in range(rows):
        row_cells = []
        for c in range(cols):
            y1 = r * cell_h + padding
            y2 = (r + 1) * cell_h - padding
            x1 = c * cell_w + padding
            x2 = (c + 1) * cell_w - padding
            # 边界保护
            y1 = max(0, y1)
            y2 = min(h, y2)
            x1 = max(0, x1)
            x2 = min(w, x2)
            if y1 >= y2 or x1 >= x2:
                logger.warning(
                    "split_grid degenerate cell [r=%d,c=%d]: padding=%d vs cell_h=%d/cell_w=%d",
                    r, c, padding, cell_h, cell_w,
                )
            row_cells.append(gray[y1:y2, x1:x2])
        cells.append(row_cells)

    return cells


def recognize_choice_group(
    gray: np.ndarray,
    region: dict,
    rows: int,
    cols: int,
    labels: list[str],
    multi_select: bool = False,
    threshold: float = 0.3,
    padding: int = 2,
    group_id: str = "",
) -> GroupResult:
    """识别一组选择题的填涂结果。

    Args:
        gray: 完整灰度图（或已裁切的区域图）
        region: 区域坐标 {"x1","y1","x2","y2"}
        rows: 题目数
        cols: 选项数
        labels: 选项标签，如 ["A","B","C","D"]
        multi_select: 是否多选
        threshold: 填涂率阈值
        padding: 网格内边距
        group_id: 题组标识

    Returns:
        GroupResult
    """
    _validate_region(region)
    # 裁切区域
    x1, y1 = region["x1"], region["y1"]
    x2, y2 = region["x2"], region["y2"]
    cropped = gray[y1:y2, x1:x2]

    # 网格切分
    cells = split_grid(cropped, rows, cols, padding)

    # 逐题识别
    question_results = []
    for r in range(rows):
        ratios = {}
        bubbles = []
        for c in range(cols):
            label = labels[c] if c < len(labels) else str(c)
            ratio = compute_fill_ratio(cells[r][c])
            ratios[label] = round(ratio, 4)
            bubbles.append(BubbleResult(
                row=r, col=c, label=label,
                fill_ratio=ratio, filled=ratio >= threshold,
            ))

        # 判定选中项
        filled_bubbles = [b for b in bubbles if b.filled]
        if multi_select:
            selected = [b.label for b in filled_bubbles]
        else:
            # 单选：取填涂率最高且超过阈值的
            if filled_bubbles:
                best = max(filled_bubbles, key=lambda b: b.fill_ratio)
                selected = [best.label]
            else:
                selected = []

        # 单选题多个选项超过阈值 → 多选异常（设计 §2）
        anomaly = not multi_select and len(filled_bubbles) > 1

        question_results.append({
            "question": r + 1,
            "selected": selected,
            "all_ratios": ratios,
            "anomaly": anomaly,
        })

    return GroupResult(group_id=group_id, question_results=question_results)


def recognize_number_fill(
    gray: np.ndarray,
    columns: list[dict],
    symbols: str = "0123456789",
    threshold: float = 0.3,
) -> str:
    """识别数字填涂区（如填涂考号）。

    Args:
        gray: 灰度图
        columns: 每列的区域坐标 [{"x1","y1","x2","y2"}, ...]
        symbols: 数字符号，默认 "0123456789"
        threshold: 填涂率阈值

    Returns:
        识别出的数字字符串，如 "0012345678"
    """
    result_digits = []
    num_symbols = len(symbols)

    for col_region in columns:
        _validate_region(col_region)
        x1, y1 = col_region["x1"], col_region["y1"]
        x2, y2 = col_region["x2"], col_region["y2"]
        col_img = gray[y1:y2, x1:x2]

        # 每列纵向分成 num_symbols 个格子
        cells = split_grid(col_img, rows=num_symbols, cols=1, padding=1)

        best_ratio = 0.0
        best_symbol = ""
        for i, row_cells in enumerate(cells):
            ratio = compute_fill_ratio(row_cells[0])
            if ratio > best_ratio:
                best_ratio = ratio
                best_symbol = symbols[i] if i < len(symbols) else "?"

        if best_ratio >= threshold:
            result_digits.append(best_symbol)
        else:
            result_digits.append("?")  # 未识别

    return "".join(result_digits)


def recognize_single_mark(
    gray: np.ndarray,
    region: dict,
    threshold: float = 0.3,
) -> bool:
    """识别单个标记（如缺考标识）。

    Args:
        gray: 灰度图
        region: 区域坐标 {"x1","y1","x2","y2"}
        threshold: 填涂率阈值

    Returns:
        是否已填涂
    """
    _validate_region(region)
    x1, y1 = region["x1"], region["y1"]
    x2, y2 = region["x2"], region["y2"]
    cell = gray[y1:y2, x1:x2]
    ratio = compute_fill_ratio(cell)
    return ratio >= threshold


def recognize_page(
    gray: np.ndarray,
    template: dict,
    threshold: float = 0.3,
) -> dict:
    """识别整页的所有填涂区域。

    Args:
        gray: 整页灰度图（已经过仿射变换校正）
        template: 模板定义，包含：
            - choice_groups: 选择题组列表
            - number_fills: 数字填涂列表（可选）
            - absent_mark: 缺考标识区域（可选）
        threshold: 填涂率阈值

    Returns:
        {
            "groups": [{"group_id": ..., "question_results": [...]}, ...],
            "numbers": {"考号": "0123456789"},
            "absent": bool,
        }
    """
    result = {"groups": [], "numbers": {}, "absent": False}

    # 选择题组
    for group_def in template.get("choice_groups", []):
        gr = recognize_choice_group(
            gray,
            region=group_def["region"],
            rows=group_def["rows"],
            cols=group_def["cols"],
            labels=group_def["labels"],
            multi_select=group_def.get("multi_select", False),
            threshold=threshold,
            group_id=group_def.get("group_id", ""),
        )
        result["groups"].append(gr)

    # 数字填涂
    for num_def in template.get("number_fills", []):
        name = num_def.get("name", "number")
        digits = recognize_number_fill(
            gray,
            columns=num_def["columns"],
            symbols=num_def.get("symbols", "0123456789"),
            threshold=threshold,
        )
        result["numbers"][name] = digits

    # 序列化 GroupResult → dict
    result["groups"] = [dataclasses.asdict(gr) for gr in result["groups"]]

    # 缺考标识
    absent_region = template.get("absent_mark")
    if absent_region:
        result["absent"] = recognize_single_mark(gray, absent_region, threshold)

    return result
