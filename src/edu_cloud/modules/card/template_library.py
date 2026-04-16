"""内置模板库 — 从 data/templates/ 加载 JSON 模板。"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# A4 单面可用文本总长度阈值（从 A4 .tpl 统计：栏高 ~1800px，2 栏，每行 40 字，行高 35px）
# 约 (1800/35) * 40 * 2 ≈ 4100 字
A4_TEXT_THRESHOLD = 4000  # 字符数，超过此值选 A3

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "templates"
_CACHE: dict[str, dict] = {}


def _load_all() -> None:
    """加载所有模板到缓存。启动时调用一次。"""
    if _CACHE:
        return
    if not _TEMPLATE_DIR.exists():
        logger.warning("模板目录不存在: %s", _TEMPLATE_DIR)
        return
    for f in _TEMPLATE_DIR.glob("月考_*_A.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            subject = data.get("subject", "")
            if subject:
                _CACHE[subject] = data
                logger.info("Loaded template: %s (%s)", subject, f.name)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("跳过损坏模板 %s: %s", f.name, e)


def list_builtin_subjects() -> list[str]:
    """返回所有内置模板的科目名列表。"""
    _load_all()
    return sorted(_CACHE.keys())


def get_builtin_template(subject: str) -> dict | None:
    """按科目名获取内置模板，不存在返回 None。"""
    _load_all()
    return _CACHE.get(subject)


def extract_fixed_parts(template: dict) -> dict:
    """从模板提取固定部分（定位点、选择题区、画布尺寸、栏配置）。

    Returns:
        {
            "anchors": [...],
            "objective_regions": [...],
            "image_size": {"width": W, "height": H},
            "columns": [{"id": "col_0", "x1": ..., "x2": ..., "y1": ..., "y2": ...}, ...],
        }
    """
    anchors = template.get("anchors", [])
    regions = template.get("regions", [])
    image_size = template.get("image_size", {})

    # 容忍历史 type 值: "objective"（旧 seed JSON）等价于 "choice_group"
    objective_regions = [r for r in regions if r.get("type") in ("objective", "choice_group")]
    subjective_regions = [r for r in regions if r.get("type") == "subjective"]

    # 从主观题 regions 推导栏配置
    columns = _derive_columns(subjective_regions, image_size)

    return {
        "anchors": anchors,
        "objective_regions": objective_regions,
        "image_size": image_size,
        "columns": columns,
    }


def _derive_columns(
    subjective_regions: list[dict], image_size: dict
) -> list[dict]:
    """从主观题区域的 x 坐标聚类推导栏配置。

    算法：按 rect.x1 排序后，x1 差值 > 阈值（image_width 的 10%）视为新栏。
    """
    if not subjective_regions:
        w = image_size.get("width", 3308)
        h = image_size.get("height", 2300)
        return [{"id": "col_0", "x1": 0, "x2": w, "y1": 0, "y2": h}]

    threshold = image_size.get("width", 3308) * 0.10
    sorted_regions = sorted(subjective_regions, key=lambda r: r["rect"]["x1"])

    clusters: list[list[dict]] = []
    current_cluster: list[dict] = [sorted_regions[0]]

    for r in sorted_regions[1:]:
        if r["rect"]["x1"] - current_cluster[-1]["rect"]["x1"] > threshold:
            clusters.append(current_cluster)
            current_cluster = [r]
        else:
            current_cluster.append(r)
    clusters.append(current_cluster)

    columns = []
    for i, cluster in enumerate(clusters):
        x1 = min(r["rect"]["x1"] for r in cluster)
        x2 = max(r["rect"]["x2"] for r in cluster)
        y1 = min(r["rect"]["y1"] for r in cluster)
        y2 = max(r["rect"]["y2"] for r in cluster)
        columns.append({"id": f"col_{i}", "x1": x1, "x2": x2, "y1": y1, "y2": y2})

    return columns


# --- .tpl 模板匹配 ---

_TPL_CACHE: list[dict] = []


def _extract_subject_from_tpl(tpl_info: dict, filename: str) -> str:
    """从 tplInfo.tpl_name 或文件名提取科目名。

    .tpl 文件中字符串常为 GBK 编码被 latin-1 读取，需要修复。
    """
    from edu_cloud.modules.card.tpl_parser import _decode_gbk
    name = tpl_info.get("tpl_name", "")
    if name:
        return _decode_gbk(name)
    # fallback: 从文件名提取（去掉编号前缀和扩展名）
    import re
    m = re.search(r'\](.+?)(?:\.|$)', filename)
    raw = m.group(1) if m else filename
    return _decode_gbk(raw)


def load_tpl_templates(tpl_dir: Path | None = None) -> list[dict]:
    """加载 .tpl 模板目录，用 tpl_parser 解析真实格式。

    Args:
        tpl_dir: 模板目录路径。None 时使用默认路径 D:/试卷数据/YueXiaoEr/Scanner/Templetes/

    Returns:
        [{"subject": str, "paper_size": str, "num_subjective": int, ...skeleton...}, ...]
    """
    from edu_cloud.modules.card.tpl_parser import parse_tpl_file

    global _TPL_CACHE
    use_default = tpl_dir is None
    if _TPL_CACHE and use_default:
        return _TPL_CACHE

    if use_default:
        tpl_dir = Path("D:/试卷数据/YueXiaoEr/Scanner/Templetes")

    if not tpl_dir.exists():
        logger.warning("TPL 模板目录不存在: %s", tpl_dir)
        return []

    templates = []
    for f in tpl_dir.glob("*.tpl"):
        try:
            # 先尝试用 tpl_parser 解析真实格式
            raw = json.loads(f.read_text(encoding="utf-8"))
            if "tplInfo" in raw:
                # 真实 .tpl 格式 → 用 parser 解析
                skeleton = parse_tpl_file(f)
                tpl_info = raw.get("tplInfo", {})
                skeleton["subject"] = _extract_subject_from_tpl(tpl_info, f.name)
                skeleton["num_subjective"] = len(skeleton.get("subjective_slots", []))
                templates.append(skeleton)
            else:
                # 简化测试格式（已有 subject/paper_size/num_subjective）
                templates.append(raw)
            logger.debug("Loaded TPL: %s", f.name)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("跳过损坏 TPL %s: %s", f.name, e)

    if use_default:
        _TPL_CACHE = templates

    return templates


def match_template(
    subject: str,
    num_subjective: int,
    paper_size: str = "A3",
    *,
    tpl_dir: Path | None = None,
) -> dict | None:
    """从 .tpl 模板中选最合适的。

    算法（设计文档 §4）:
    1. 按科目筛选
    2. 按纸张规格筛选（无则用全部候选）
    3. 按主观题数量最接近排序

    Returns:
        最佳模板 dict，或 None（无该科目模板）
    """
    all_tpls = load_tpl_templates(tpl_dir)
    if not all_tpls:
        return None

    # 1. 科目筛选
    candidates = [t for t in all_tpls if t.get("subject") == subject]
    if not candidates:
        return None

    # 2. 纸张规格筛选
    same_paper = [t for t in candidates if t.get("paper_size") == paper_size]
    if same_paper:
        candidates = same_paper

    # 3. 按主观题数量最接近排序
    candidates.sort(key=lambda t: abs(t.get("num_subjective", 0) - num_subjective))
    return candidates[0]
