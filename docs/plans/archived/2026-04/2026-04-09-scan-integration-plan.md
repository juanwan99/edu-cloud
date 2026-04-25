<!-- pre-takeover: archived for history, not active spec -->
# paper-seg 整合到 edu-cloud 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 paper-seg 的视觉处理模块和切割流水线整合到 edu-cloud，在考试详情页的"扫描状态"tab 实现一站式扫描切割。

**Architecture:** 复制 paper-seg 的 6 个 vision 文件到 `scan/vision/`，新建 `tpl_parser.py`（tpl 解析）和 `pipeline_service.py`（流水线服务），新建 `pipeline_router.py`（API 端点），前端在 ExamDetailPage 的扫描 tab 实现操作界面。

**Tech Stack:** FastAPI, OpenCV (headless), pyzbar, Pillow, numpy, Vue 3, Naive UI

**Design:** `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-design.md`

---

### Task 1: 安装依赖 + 迁移 vision 模块

**Files:**
- Modify: `pyproject.toml`
- Create: `src/edu_cloud/modules/scan/vision/__init__.py`
- Create: `src/edu_cloud/modules/scan/vision/anchors.py`
- Create: `src/edu_cloud/modules/scan/vision/transform.py`
- Create: `src/edu_cloud/modules/scan/vision/segment.py`
- Create: `src/edu_cloud/modules/scan/vision/barcode.py`
- Create: `src/edu_cloud/modules/scan/vision/fillmark.py`
- Create: `src/edu_cloud/modules/scan/vision/lines.py`
- Test: `tests/test_services_exam/test_scan_vision.py`

- [ ] **Step 1: 安装依赖**

```bash
cd C:/Users/Administrator/edu-cloud
pip install opencv-python-headless pyzbar
```

在 `pyproject.toml` 的 dependencies 中追加：
```toml
"opencv-python-headless>=4.8",
"pyzbar>=0.1.9",
```

- [ ] **Step 2: 复制 vision 模块**

```bash
mkdir -p src/edu_cloud/modules/scan/vision
cp C:/Users/Administrator/paper-seg/app/vision/anchors.py src/edu_cloud/modules/scan/vision/
cp C:/Users/Administrator/paper-seg/app/vision/transform.py src/edu_cloud/modules/scan/vision/
cp C:/Users/Administrator/paper-seg/app/vision/segment.py src/edu_cloud/modules/scan/vision/
cp C:/Users/Administrator/paper-seg/app/vision/barcode.py src/edu_cloud/modules/scan/vision/
cp C:/Users/Administrator/paper-seg/app/vision/fillmark.py src/edu_cloud/modules/scan/vision/
cp C:/Users/Administrator/paper-seg/app/vision/lines.py src/edu_cloud/modules/scan/vision/
```

- [ ] **Step 3: 创建 `__init__.py`**

```python
"""扫描视觉处理模块 — 从 paper-seg 迁入。"""
from .anchors import detect_anchors
from .transform import compute_affine, transform_rect
from .segment import crop_region
from .barcode import read_barcode
from .fillmark import recognize_page
from .lines import detect_lines

__all__ = [
    "detect_anchors", "compute_affine", "transform_rect",
    "crop_region", "read_barcode", "recognize_page", "detect_lines",
]
```

- [ ] **Step 4: 修复 import 路径**

`segment.py` 内部导入了 `from app.vision.anchors import ...` 和 `from app.vision.transform import ...`，需要改为：
```python
from .anchors import detect_anchors
from .transform import compute_affine, transform_rect
```

检查其他文件是否有类似的 `app.vision.` 前缀，全部改为相对导入。

- [ ] **Step 5: 写 vision 测试**

创建 `tests/test_services_exam/test_scan_vision.py`：

```python
"""Vision 模块基础测试 — 验证导入和核心函数签名。"""
import pytest
import numpy as np
from PIL import Image


class TestVisionImport:
    def test_all_modules_importable(self):
        from edu_cloud.modules.scan.vision import (
            detect_anchors, compute_affine, transform_rect,
            crop_region, read_barcode, recognize_page, detect_lines,
        )
        assert callable(detect_anchors)
        assert callable(crop_region)

    def test_detect_anchors_empty_image(self):
        from edu_cloud.modules.scan.vision import detect_anchors
        gray = np.zeros((100, 100), dtype=np.uint8)
        result = detect_anchors(gray)
        assert isinstance(result, list)
        assert len(result) == 0  # 空图无定位点

    def test_crop_region(self):
        from edu_cloud.modules.scan.vision import crop_region
        img = Image.new("RGB", (200, 200), (255, 255, 255))
        rect = {"x1": 10, "y1": 20, "x2": 100, "y2": 80}
        cropped = crop_region(img, rect)
        assert cropped.size == (90, 60)

    def test_compute_affine_insufficient_points(self):
        from edu_cloud.modules.scan.vision import compute_affine
        src = [{"cx": 10, "cy": 10, "id": "TL"}]
        dst = [{"cx": 20, "cy": 20, "id": "TL"}]
        result = compute_affine(src, dst)
        assert result is None  # 需要至少 3 个点
```

- [ ] **Step 6: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_scan_vision.py -v`
Expected: 4 passed

- [ ] **Step 7: 用真实扫描图测试定位点检测**

```python
# 追加到 test_scan_vision.py
import os

class TestVisionWithRealImage:
    @pytest.mark.skipif(
        not os.path.exists(r"D:\试卷数据\试卷图像\191871\A3722\地理\I0101000001A.png"),
        reason="Real scan images not available",
    )
    def test_detect_anchors_real_image(self):
        from edu_cloud.modules.scan.vision import detect_anchors
        img = Image.open(r"D:\试卷数据\试卷图像\191871\A3722\地理\I0101000001A.png").convert("L")
        gray = np.array(img)
        anchors = detect_anchors(gray)
        assert len(anchors) == 4
        ids = {a["id"] for a in anchors}
        assert ids == {"TL", "TR", "BL", "BR"}
```

- [ ] **Step 8: 运行全部测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_scan_vision.py -v`
Expected: 5 passed (或 4 passed + 1 skipped)

- [ ] **Step 9: Commit**

```bash
git add src/edu_cloud/modules/scan/vision/ tests/test_services_exam/test_scan_vision.py pyproject.toml
git commit -m "feat: migrate paper-seg vision module to edu-cloud scan"
```

**审查清单:**
- ✓ 所有 6 个 vision 文件可导入
- ✓ 无 `app.vision.` 残留引用
- ✗ 空图像不崩溃

---

### Task 2: tpl 模板解析器

**Files:**
- Create: `src/edu_cloud/modules/scan/tpl_parser.py`
- Test: `tests/test_services_exam/test_tpl_parser.py`

- [ ] **Step 1: 写 tpl 解析测试**

创建 `tests/test_services_exam/test_tpl_parser.py`：

```python
"""tpl 模板文件解析测试。"""
import pytest


FAKE_TPL = {
    "tplInfo": {"iwidth": 3299, "iheight": 2289, "tpl_name": "地理"},
    "datas": {
        "tplLocsList": [
            {"loc_no": "0101", "location": "(67,71)-(125,112)", "inpage": 0, "busing": True, "loc_name": "1页左上"},
            {"loc_no": "0102", "location": "(1121,73)-(1179,115)", "inpage": 0, "busing": True, "loc_name": "1页右上"},
            {"loc_no": "0103", "location": "(1116,2189)-(1174,2230)", "inpage": 0, "busing": True, "loc_name": "1页右下"},
            {"loc_no": "0104", "location": "(64,2187)-(122,2228)", "inpage": 0, "busing": True, "loc_name": "1页左下"},
        ],
        "tplSubqueList": [
            {"que_no": "07001", "que_name": "17题(1)", "location": "(88,1015)-(1169,1677)", "inpage": 0, "score_val": "6", "busing": 1, "que_type": "解答题"},
            {"que_no": "07002", "que_name": "17题(2)", "location": "(93,1579)-(1174,2192)", "inpage": 0, "score_val": "4", "busing": 1, "que_type": "解答题"},
        ],
        "tplObjqueGList": [
            {"qg_no": "06001", "qg_name": "单选", "location": "(161,833)-(384,935)", "opt_count": 4, "que_count": 5, "opt_symbol": "A,B,C,D", "inpage": 0, "qg_indexno": 1, "direction": "纵向排列"},
        ],
        "MbNoBarCodeList": [
            {"bc_no": "0310", "bc_name": "条码考号", "location": "(678,231)-(1175,509)", "inpage": 0, "busing": True},
        ],
        "tplUnexamList": [
            {"unexam_no": "0401", "unexam_name": "缺考标识", "location": "(932,650)-(962,667)", "inpage": 0, "busing": True, "iwidth": 31, "iheight": 18},
        ],
    },
}


class TestParseLocation:
    def test_parse_normal(self):
        from edu_cloud.modules.scan.tpl_parser import _parse_tpl_location
        result = _parse_tpl_location("(88,1015)-(1169,1677)")
        assert result == {"x1": 88, "y1": 1015, "x2": 1169, "y2": 1677}

    def test_parse_zero(self):
        from edu_cloud.modules.scan.tpl_parser import _parse_tpl_location
        result = _parse_tpl_location("(0,0)-(0,0)")
        assert result == {"x1": 0, "y1": 0, "x2": 0, "y2": 0}


class TestConvertTpl:
    def test_anchors(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert len(result["anchors"]) == 4
        ids = {a["id"] for a in result["anchors"]}
        assert ids == {"TL", "TR", "BR", "BL"}
        tl = next(a for a in result["anchors"] if a["id"] == "TL")
        assert tl["cx"] == (67 + 125) // 2
        assert tl["cy"] == (71 + 112) // 2

    def test_subjective_regions(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        subj = [r for r in result["regions"] if r["type"] == "subjective"]
        assert len(subj) == 2
        assert subj[0]["name"] == "17题(1)"
        assert subj[0]["rect"] == {"x1": 88, "y1": 1015, "x2": 1169, "y2": 1677}
        assert subj[0]["score"] == 6

    def test_objective_regions(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        obj = [r for r in result["regions"] if r["type"] == "choice_group"]
        assert len(obj) == 1
        assert obj[0]["cols"] == 4
        assert obj[0]["rows"] == 5
        assert obj[0]["labels"] == ["A", "B", "C", "D"]

    def test_image_size(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert result["image_size"] == {"width": 3299, "height": 2289}

    def test_barcode_region(self):
        from edu_cloud.modules.scan.tpl_parser import convert_tpl
        result = convert_tpl(FAKE_TPL)
        assert result["barcode_region"] == {"x1": 678, "y1": 231, "x2": 1175, "y2": 509}


class TestParseTplFile:
    @pytest.mark.skipif(
        not __import__("os").path.exists(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl"),
        reason="Real tpl file not available",
    )
    def test_parse_real_tpl(self):
        from edu_cloud.modules.scan.tpl_parser import parse_tpl_file
        result = parse_tpl_file(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl")
        assert len(result["anchors"]) == 4
        subj = [r for r in result["regions"] if r["type"] == "subjective"]
        assert len(subj) == 10  # 地理 10 个主观题区域
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 tpl_parser.py**

创建 `src/edu_cloud/modules/scan/tpl_parser.py`：

```python
"""tpl 模板文件解析器 — 将外部 .tpl JSON 转换为 edu-cloud Template 格式。"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 定位点 ID 映射
_LOC_ID_MAP = {"0101": "TL", "0102": "TR", "0103": "BR", "0104": "BL"}


def _parse_tpl_location(loc_str: str) -> dict:
    """解析 tpl 坐标格式 '(x1,y1)-(x2,y2)' → {x1, y1, x2, y2}。"""
    m = re.match(r"\((\d+),(\d+)\)-\((\d+),(\d+)\)", loc_str)
    if not m:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    return {"x1": int(m[1]), "y1": int(m[2]), "x2": int(m[3]), "y2": int(m[4])}


def convert_tpl(tpl_data: dict, page: int | None = None) -> dict:
    """将 .tpl JSON 数据转换为 edu-cloud 模板格式。

    Args:
        tpl_data: 原始 .tpl JSON（含 tplInfo + datas）
        page: None=全部页, 0=A面, 1=B面

    Returns:
        {image_size, anchors[], regions[], barcode_region, tpl_name}
    """
    info = tpl_data.get("tplInfo", {})
    datas = tpl_data.get("datas", {})

    # 定位点
    anchors = []
    for loc in datas.get("tplLocsList", []):
        if page is not None and loc.get("inpage", 0) != page:
            continue
        if not loc.get("busing", True):
            continue
        loc_id = _LOC_ID_MAP.get(loc.get("loc_no", ""), loc.get("loc_name", ""))
        rect = _parse_tpl_location(loc["location"])
        anchors.append({
            "id": loc_id,
            "x": rect["x1"], "y": rect["y1"],
            "w": rect["x2"] - rect["x1"], "h": rect["y2"] - rect["y1"],
            "cx": (rect["x1"] + rect["x2"]) // 2,
            "cy": (rect["y1"] + rect["y2"]) // 2,
        })

    # 主观题区域
    regions = []
    for i, q in enumerate(datas.get("tplSubqueList", [])):
        if page is not None and q.get("inpage", 0) != page:
            continue
        if not q.get("busing", 1):
            continue
        rect = _parse_tpl_location(q["location"])
        score_str = q.get("score_val", "0")
        score = int(score_str) if score_str.isdigit() else 0
        regions.append({
            "id": f"Q{i + 1:02d}",
            "name": q.get("que_name", f"题{i + 1}"),
            "type": "subjective",
            "rect": rect,
            "page": q.get("inpage", 0),
            "score": score,
        })

    # 选择题组
    for i, g in enumerate(datas.get("tplObjqueGList", [])):
        if page is not None and g.get("inpage", 0) != page:
            continue
        if not g.get("busing", True):
            continue
        rect = _parse_tpl_location(g["location"])
        labels = [s.strip() for s in g.get("opt_symbol", "A,B,C,D").split(",")]
        regions.append({
            "id": f"OBJ{i + 1:02d}",
            "name": g.get("qg_name", f"选择题组{i + 1}"),
            "type": "choice_group",
            "rect": rect,
            "page": g.get("inpage", 0),
            "score": 0,
            "cols": g.get("opt_count", 4),
            "rows": g.get("que_count", 1),
            "labels": labels,
            "multi_select": g.get("opt_type", "") == "多选",
            "qg_indexno": g.get("qg_indexno", 1),
        })

    # 条码区域
    barcode_region = None
    for bc in datas.get("MbNoBarCodeList", []):
        if bc.get("busing", True):
            barcode_region = _parse_tpl_location(bc["location"])
            break

    return {
        "image_size": {"width": info.get("iwidth", 0), "height": info.get("iheight", 0)},
        "anchors": anchors,
        "regions": regions,
        "barcode_region": barcode_region,
        "tpl_name": info.get("tpl_name", ""),
    }


def parse_tpl_file(path: str | Path) -> dict:
    """解析 .tpl 文件并返回模板数据。"""
    with open(str(path), "r", encoding="utf-8") as f:
        tpl_data = json.load(f)
    result = convert_tpl(tpl_data)
    logger.info("parse_tpl_file: %s → %d anchors, %d regions",
                path, len(result["anchors"]), len(result["regions"]))
    return result
```

- [ ] **Step 4: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_tpl_parser.py -v`
Expected: 7 passed (或 6 passed + 1 skipped)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/scan/tpl_parser.py tests/test_services_exam/test_tpl_parser.py
git commit -m "feat: tpl template parser for scan pipeline"
```

**审查清单:**
- ✓ 定位点 ID 映射正确（0101→TL, 0102→TR, 0103→BR, 0104→BL）
- ✓ 主观题和选择题组都能解析
- ✓ 条码区域提取
- ✗ 无效坐标格式不崩溃（返回全零）

---

### Task 3: 流水线服务

**Files:**
- Create: `src/edu_cloud/modules/scan/pipeline_service.py`
- Test: `tests/test_services_exam/test_scan_pipeline.py`

- [ ] **Step 1: 写流水线测试**

创建 `tests/test_services_exam/test_scan_pipeline.py`：

```python
"""扫描流水线服务测试。"""
import pytest
import os
import tempfile
from pathlib import Path
from PIL import Image


@pytest.fixture
def fake_scan_dir(tmp_path):
    """创建包含假扫描图片的临时目录。"""
    for i in range(3):
        img = Image.new("RGB", (200, 150), (255, 255, 255))
        img.save(tmp_path / f"I010100000{i + 1}A.png")
    return str(tmp_path)


@pytest.fixture
def fake_template():
    """最小模板（无定位点，两个裁切区域）。"""
    return {
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [
            {"id": "Q01", "name": "1题", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "score": 5},
            {"id": "Q02", "name": "2题", "type": "subjective", "rect": {"x1": 10, "y1": 80, "x2": 90, "y2": 140}, "score": 5},
        ],
        "barcode_region": None,
    }


class TestListScanImages:
    def test_list_png_files(self, fake_scan_dir):
        from edu_cloud.modules.scan.pipeline_service import list_scan_images
        files = list_scan_images(fake_scan_dir, side="A")
        assert len(files) == 3
        assert all(f.name.endswith("A.png") for f in files)

    def test_list_empty_dir(self, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import list_scan_images
        files = list_scan_images(str(tmp_path), side="A")
        assert files == []

    def test_list_nonexistent_dir(self):
        from edu_cloud.modules.scan.pipeline_service import list_scan_images
        with pytest.raises(FileNotFoundError):
            list_scan_images("/nonexistent/path", side="A")


class TestProcessOneImage:
    def test_crop_without_anchors(self, fake_scan_dir, fake_template, tmp_path):
        """无定位点时用缩放比裁切。"""
        from edu_cloud.modules.scan.pipeline_service import process_one_image
        image_path = Path(fake_scan_dir) / "I0101000001A.png"
        result = process_one_image(image_path, fake_template, str(tmp_path))
        assert result["student_id"] == "I0101000001"  # 从文件名提取
        assert len(result["crops"]) == 2
        assert result["errors"] == []
        # 检查切图文件存在
        for crop in result["crops"]:
            assert os.path.exists(crop["path"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_scan_pipeline.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 pipeline_service.py**

创建 `src/edu_cloud/modules/scan/pipeline_service.py`：

```python
"""扫描流水线服务 — 批量切割扫描图并存入 StudentAnswer。"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
import numpy as np

from .vision import detect_anchors, crop_region, read_barcode

logger = logging.getLogger(__name__)


@dataclass
class PipelineProgress:
    total: int = 0
    processed: int = 0
    failed: int = 0
    current_file: str = ""
    warnings: list = field(default_factory=list)
    status: str = "idle"  # idle, running, completed, stopped, failed


# 全局进度和锁
_progress: dict[str, PipelineProgress] = {}
_lock = asyncio.Lock()
_running = False


def get_progress(pipeline_id: str = "default") -> dict:
    p = _progress.get(pipeline_id, PipelineProgress())
    return {
        "status": p.status,
        "total": p.total,
        "processed": p.processed,
        "failed": p.failed,
        "current_file": p.current_file,
        "warnings": p.warnings[-50:],  # 最近 50 条
    }


def is_running() -> bool:
    return _running


def request_stop():
    global _running
    _running = False


def list_scan_images(image_dir: str, side: str = "A") -> list[Path]:
    """列出扫描目录下指定面的 PNG 文件。"""
    d = Path(image_dir)
    if not d.exists():
        raise FileNotFoundError(f"目录不存在: {image_dir}")
    pattern = f"*{side}.png"
    files = sorted(d.glob(pattern))
    return files


def _extract_student_id(filename: str) -> str:
    """从文件名提取学生 ID。去掉面标识(A/B)和扩展名。"""
    name = Path(filename).stem  # I0101000001A → I0101000001A
    if name and name[-1] in ("A", "B"):
        return name[:-1]
    return name


def process_one_image(
    image_path: Path,
    template: dict,
    output_dir: str,
    barcode_region: dict | None = None,
) -> dict:
    """处理单张扫描图：检测定位点 → 缩放裁切 → 保存切图。

    Returns:
        {student_id, crops: [{region_id, name, path, size}], errors: [str]}
    """
    img = Image.open(str(image_path)).convert("RGB")
    gray = np.array(img.convert("L"))
    img_w, img_h = img.size

    # 条码识别
    student_id = None
    if barcode_region:
        try:
            student_id = read_barcode(image_path, barcode_region)
        except Exception:
            pass
    if not student_id:
        student_id = _extract_student_id(image_path.name)

    # 模板尺寸 → 缩放比
    tpl_size = template.get("image_size", {})
    tpl_w = tpl_size.get("width", img_w)
    tpl_h = tpl_size.get("height", img_h)
    sx = img_w / tpl_w if tpl_w > 0 else 1.0
    sy = img_h / tpl_h if tpl_h > 0 else 1.0

    # 裁切每个主观题区域
    crops = []
    errors = []
    subjective = [r for r in template.get("regions", []) if r.get("type") == "subjective"]
    stu_dir = os.path.join(output_dir, student_id)
    os.makedirs(stu_dir, exist_ok=True)

    for region in subjective:
        try:
            rect = region["rect"]
            scaled_rect = {
                "x1": int(rect["x1"] * sx),
                "y1": int(rect["y1"] * sy),
                "x2": int(rect["x2"] * sx),
                "y2": int(rect["y2"] * sy),
            }
            cropped = crop_region(img, scaled_rect)
            out_path = os.path.join(stu_dir, f"{region['id']}.png")
            cropped.save(out_path)
            crops.append({
                "region_id": region["id"],
                "name": region.get("name", region["id"]),
                "path": out_path,
                "size": cropped.size,
            })
        except Exception as e:
            errors.append(f"Region {region['id']}: {e}")

    return {"student_id": student_id, "crops": crops, "errors": errors}


async def run_pipeline(
    image_dir: str,
    template: dict,
    output_dir: str,
    exam_id: str,
    subject_id: str,
    school_id: str,
    side: str = "A",
    pipeline_id: str = "default",
    save_answer_fn=None,
) -> dict:
    """异步运行批量切割流水线。

    Args:
        save_answer_fn: async fn(exam_id, subject_id, student_id, question_id, image_path, school_id)
            用于将切图保存到 StudentAnswer 表。None 时只切不存。
    """
    global _running

    async with _lock:
        if _running:
            raise RuntimeError("流水线正在运行")
        _running = True

    files = list_scan_images(image_dir, side)
    progress = PipelineProgress(total=len(files), status="running")
    _progress[pipeline_id] = progress

    barcode_region = template.get("barcode_region")
    results = {"total": len(files), "processed": 0, "failed": 0, "students": []}

    try:
        for f in files:
            if not _running:
                progress.status = "stopped"
                break

            progress.current_file = f.name
            try:
                result = process_one_image(f, template, output_dir, barcode_region)
                progress.processed += 1
                results["processed"] += 1
                results["students"].append(result["student_id"])

                if result["errors"]:
                    for e in result["errors"]:
                        progress.warnings.append({"file": f.name, "message": e})

                # 保存到数据库
                if save_answer_fn:
                    for crop in result["crops"]:
                        await save_answer_fn(
                            exam_id=exam_id,
                            subject_id=subject_id,
                            student_id=result["student_id"],
                            question_id=crop["region_id"],
                            image_path=crop["path"],
                            school_id=school_id,
                        )
            except Exception as e:
                progress.failed += 1
                results["failed"] += 1
                progress.warnings.append({"file": f.name, "message": str(e)})
                logger.error("Pipeline error for %s: %s", f.name, e)

            # 让出事件循环
            await asyncio.sleep(0)

        if _running:
            progress.status = "completed"
    finally:
        _running = False

    logger.info("Pipeline finished: %d/%d processed, %d failed",
                results["processed"], results["total"], results["failed"])
    return results
```

- [ ] **Step 4: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_scan_pipeline.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_service.py tests/test_services_exam/test_scan_pipeline.py
git commit -m "feat: scan pipeline service with batch crop"
```

**审查清单:**
- ✓ 文件名提取 student_id（去掉 A/B 后缀）
- ✓ 缩放比裁切（模板尺寸 vs 扫描图尺寸）
- ✓ 并发锁防止多次启动
- ✓ 进度追踪（total/processed/failed/current_file）
- ✗ 不存在的目录抛 FileNotFoundError

---

### Task 4: 流水线 API 端点

**Files:**
- Create: `src/edu_cloud/modules/scan/pipeline_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_scan_pipeline_api.py`

- [ ] **Step 1: 实现 pipeline_router.py**

创建 `src/edu_cloud/modules/scan/pipeline_router.py`：

```python
"""扫描流水线 API 端点。"""
import asyncio
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.shared.storage import get_storage, StorageService
from . import pipeline_service
from .tpl_parser import parse_tpl_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scan/pipeline", tags=["scan-pipeline"])


class StartPipelineRequest(BaseModel):
    subject_id: str
    side: str = "A"
    image_dir: str
    tpl_path: str | None = None  # 可选：.tpl 文件路径（替代 Template 表）


class ImportTplRequest(BaseModel):
    tpl_path: str
    subject_id: str
    side: str = "A"


class PreviewRequest(BaseModel):
    image_path: str
    subject_id: str
    side: str = "A"


@router.post("/start")
async def start_pipeline(
    req: StartPipelineRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
    storage: StorageService = Depends(get_storage),
):
    """启动扫描切割流水线。"""
    school_id = current["current_role"].school_id

    if pipeline_service.is_running():
        raise HTTPException(409, "流水线正在运行")

    # 验证目录
    if not os.path.isdir(req.image_dir):
        raise HTTPException(400, f"目录不存在: {req.image_dir}")

    # 获取 subject + exam
    subject = (await db.execute(
        select(Subject).where(Subject.id == req.subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    # 加载模板
    if req.tpl_path:
        if not os.path.isfile(req.tpl_path):
            raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")
        template = parse_tpl_file(req.tpl_path)
    else:
        tpl = (await db.execute(
            select(Template).where(
                Template.subject_id == req.subject_id,
                Template.side == req.side,
                Template.school_id == school_id,
            )
        )).scalar_one_or_none()
        if not tpl:
            raise HTTPException(404, "模板不存在，请先发布答题卡或导入 .tpl 文件")
        template = {
            "image_size": {"width": tpl.image_width, "height": tpl.image_height},
            "anchors": tpl.anchors or [],
            "regions": tpl.regions or [],
            "barcode_region": None,
        }

    # 列出文件
    try:
        files = pipeline_service.list_scan_images(req.image_dir, req.side)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

    if not files:
        raise HTTPException(400, f"目录下没有 {req.side} 面的 PNG 文件")

    output_dir = storage.root

    # 保存到 StudentAnswer 的回调
    async def save_answer(exam_id, subject_id, student_id, question_id, image_path, school_id):
        from sqlalchemy.exc import IntegrityError
        from edu_cloud.database import async_session
        async with async_session() as session:
            answer = StudentAnswer(
                exam_id=exam_id, subject_id=subject_id, student_id=student_id,
                question_id=question_id, image_path=image_path, school_id=school_id,
            )
            session.add(answer)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()  # 重复数据跳过

    # 后台启动
    asyncio.create_task(pipeline_service.run_pipeline(
        image_dir=req.image_dir,
        template=template,
        output_dir=output_dir,
        exam_id=subject.exam_id,
        subject_id=req.subject_id,
        school_id=school_id,
        side=req.side,
        save_answer_fn=save_answer,
    ))

    logger.info("Pipeline started: subject=%s, dir=%s, files=%d",
                subject.name, req.image_dir, len(files))
    return {"status": "started", "total_files": len(files)}


@router.get("/progress")
async def get_progress():
    """获取流水线进度。"""
    return pipeline_service.get_progress()


@router.post("/stop")
async def stop_pipeline():
    """停止流水线。"""
    if not pipeline_service.is_running():
        raise HTTPException(400, "流水线未在运行")
    pipeline_service.request_stop()
    return {"status": "stopping"}


@router.post("/preview")
async def preview_scan(
    req: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """预览单张扫描图的切割区域标注。"""
    import base64
    from PIL import ImageDraw
    from io import BytesIO

    school_id = current["current_role"].school_id

    if not os.path.isfile(req.image_path):
        raise HTTPException(400, f"文件不存在: {req.image_path}")

    # 加载模板
    tpl = (await db.execute(
        select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
            Template.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not tpl:
        raise HTTPException(404, "模板不存在")

    img = Image.open(req.image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    sx = img_w / (tpl.image_width or img_w)
    sy = img_h / (tpl.image_height or img_h)

    # 标注定位点（红框）
    from .vision import detect_anchors
    import numpy as np
    gray = np.array(img.convert("L"))
    anchors = detect_anchors(gray)
    for a in anchors:
        x, y, w, h = a["x"], a["y"], a["w"], a["h"]
        draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
        draw.text((x, y - 12), a["id"], fill="red")

    # 标注切割区域（蓝框）
    for r in (tpl.regions or []):
        rect = r.get("rect", {})
        x1 = int(rect.get("x1", 0) * sx)
        y1 = int(rect.get("y1", 0) * sy)
        x2 = int(rect.get("x2", 0) * sx)
        y2 = int(rect.get("y2", 0) * sy)
        color = "blue" if r.get("type") == "subjective" else "green"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        draw.text((x1 + 2, y1 + 2), r.get("name", r.get("id", "")), fill=color)

    # 缩小图片（原图太大）
    max_w = 1200
    if img_w > max_w:
        ratio = max_w / img_w
        img = img.resize((max_w, int(img_h * ratio)))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {"image": f"data:image/jpeg;base64,{b64}", "anchors": len(anchors)}


@router.post("/import-tpl")
async def import_tpl(
    req: ImportTplRequest,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """导入 .tpl 文件到 Template 表。"""
    school_id = current["current_role"].school_id

    if not os.path.isfile(req.tpl_path):
        raise HTTPException(400, f"tpl 文件不存在: {req.tpl_path}")

    subject = (await db.execute(
        select(Subject).where(Subject.id == req.subject_id, Subject.school_id == school_id)
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "科目不存在")

    tpl_data = parse_tpl_file(req.tpl_path)

    # Upsert Template
    existing = (await db.execute(
        select(Template).where(
            Template.subject_id == req.subject_id,
            Template.side == req.side,
            Template.school_id == school_id,
        )
    )).scalar_one_or_none()

    values = {
        "image_width": tpl_data["image_size"]["width"],
        "image_height": tpl_data["image_size"]["height"],
        "anchors": tpl_data["anchors"],
        "regions": tpl_data["regions"],
    }

    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        existing = Template(
            subject_id=req.subject_id, side=req.side, school_id=school_id, **values,
        )
        db.add(existing)

    await db.commit()
    await db.refresh(existing)
    logger.info("import_tpl: subject=%s, side=%s, regions=%d", subject.name, req.side, len(tpl_data["regions"]))
    return {"id": existing.id, "regions": len(tpl_data["regions"]), "anchors": len(tpl_data["anchors"])}
```

- [ ] **Step 2: 在 app.py 注册 pipeline_router**

在 `src/edu_cloud/api/app.py` 的路由注册区域添加：

```python
    from edu_cloud.modules.scan.pipeline_router import router as scan_pipeline_router
```

并加入 `for r in [...]` 列表。

- [ ] **Step 3: 写 API 测试**

创建 `tests/test_api/test_scan_pipeline_api.py`：

```python
"""扫描流水线 API 测试。"""
import pytest
from httpx import AsyncClient
from PIL import Image
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def scan_seed(client: AsyncClient, db, tmp_path):
    """创建扫描测试种子数据 + 假扫描目录。"""
    school = School(id="scan_s1", name="扫描测试校", code="SCAN01")
    db.add(school)
    await db.commit()

    user = User(id="scan_u1", username="scan_user", display_name="扫描用户")
    user.set_password("pass123")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id="scan_u1", role="principal", school_id="scan_s1", is_primary=True))
    await db.commit()

    exam = Exam(id="scan_e1", name="扫描测试考试", school_id="scan_s1")
    db.add(exam)
    await db.commit()

    subject = Subject(id="scan_sub1", exam_id="scan_e1", name="地理", code="DL", school_id="scan_s1")
    db.add(subject)
    await db.commit()

    # 创建假扫描图
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    for i in range(3):
        img = Image.new("RGB", (200, 150), (240, 240, 240))
        img.save(scan_dir / f"STU{i + 1:03d}A.png")

    token = create_access_token({"sub": "scan_u1", "role": "principal", "active_role_id": "dummy"})
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "headers": headers,
        "scan_dir": str(scan_dir),
        "subject_id": "scan_sub1",
        "exam_id": "scan_e1",
    }


class TestPipelineProgress:
    async def test_progress_idle(self, client: AsyncClient, scan_seed):
        resp = await client.get("/api/v1/scan/pipeline/progress", headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("idle", "completed")

    async def test_start_no_template(self, client: AsyncClient, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": scan_seed["scan_dir"],
        }, headers=scan_seed["headers"])
        assert resp.status_code == 404
        assert "模板不存在" in resp.json()["detail"]

    async def test_start_nonexistent_dir(self, client: AsyncClient, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/start", json={
            "subject_id": scan_seed["subject_id"],
            "side": "A",
            "image_dir": "/nonexistent/dir",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 400


class TestImportTpl:
    @pytest.mark.skipif(
        not __import__("os").path.exists(r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl"),
        reason="Real tpl file not available",
    )
    async def test_import_real_tpl(self, client: AsyncClient, scan_seed):
        resp = await client.post("/api/v1/scan/pipeline/import-tpl", json={
            "tpl_path": r"D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl",
            "subject_id": scan_seed["subject_id"],
            "side": "A",
        }, headers=scan_seed["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["regions"] == 10
        assert data["anchors"] == 4
```

- [ ] **Step 4: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_scan_pipeline_api.py -v`
Expected: 4 passed (或 3 passed + 1 skipped)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_router.py src/edu_cloud/api/app.py tests/test_api/test_scan_pipeline_api.py
git commit -m "feat: scan pipeline API endpoints"
```

**审查清单:**
- ✓ 启动时校验目录和模板存在
- ✓ 后台异步运行（asyncio.create_task）
- ✓ 进度轮询端点
- ✓ 预览返回标注图（base64）
- ✓ tpl 导入写入 Template 表
- ✗ 重复启动返回 409

---

### Task 5: 前端扫描 Tab

**Files:**
- Create: `frontend/src/api/scan.js`
- Modify: `frontend/src/pages/ExamDetailPage.vue`

- [ ] **Step 1: 创建 scan.js API 层**

创建 `frontend/src/api/scan.js`：

```javascript
import client from './client'

export const startPipeline = (subjectId, side, imageDir, tplPath = null) =>
  client.post('/scan/pipeline/start', {
    subject_id: subjectId,
    side,
    image_dir: imageDir,
    tpl_path: tplPath,
  })

export const getPipelineProgress = () =>
  client.get('/scan/pipeline/progress')

export const stopPipeline = () =>
  client.post('/scan/pipeline/stop')

export const previewScan = (imagePath, subjectId, side) =>
  client.post('/scan/pipeline/preview', {
    image_path: imagePath,
    subject_id: subjectId,
    side,
  })

export const importTpl = (tplPath, subjectId, side) =>
  client.post('/scan/pipeline/import-tpl', {
    tpl_path: tplPath,
    subject_id: subjectId,
    side,
  })
```

- [ ] **Step 2: 修改 ExamDetailPage.vue 扫描 Tab**

在 ExamDetailPage.vue 的"扫描状态"tab 面板（当前显示空白或占位内容）中，添加扫描切割操作界面：

1. 科目选择下拉框（复用已有的 subjects 数据）
2. 面选择（A/B radio）
3. 扫描目录输入框
4. 模板状态显示（已发布/未发布 + 导入 .tpl 按钮）
5. 预览按钮 + 预览图展示区
6. 开始/停止按钮
7. 进度条 + 统计信息
8. 警告列表

关键逻辑：
- 选择科目后检查 Template 是否存在（GET `/api/v1/templates/{subject_id}/A`）
- 点"预览"发送目录第一张图路径到 preview 端点，显示标注图
- 点"开始"调 start，然后每 2 秒轮询 progress 更新进度条
- 完成后显示汇总（成功/失败/警告）

具体 Vue 代码由 Executor 根据项目已有的 Naive UI 组件模式实现（NSelect、NInput、NButton、NProgress、NAlert）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/scan.js frontend/src/pages/ExamDetailPage.vue
git commit -m "feat: scan tab UI with pipeline controls"
```

**审查清单:**
- ✓ 科目下拉复用 subjects 数据
- ✓ 进度轮询 2 秒间隔
- ✓ 完成后停止轮询
- ✓ 错误和警告有用户提示
- ✗ 未选科目/未输入路径时按钮禁用

---

### Task 6: 端到端集成测试 + 全量回归

**Files:** 无新文件

- [ ] **Step 1: 运行 vision 测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services_exam/test_scan_vision.py tests/test_services_exam/test_tpl_parser.py tests/test_services_exam/test_scan_pipeline.py -v`
Expected: all passed

- [ ] **Step 2: 运行 API 测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_scan_pipeline_api.py tests/test_api/test_compat.py -v`
Expected: all passed

- [ ] **Step 3: 运行全量后端测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 1590+ passed

- [ ] **Step 4: 运行前端测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: all passed

- [ ] **Step 5: 启动服务端到端验证**

```bash
cd C:/Users/Administrator/edu-cloud
python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 127.0.0.1 --port 9000 --reload
```

手动验证：
1. 登录 → 考试详情 → 扫描状态 tab
2. 选择科目（地理）→ 导入 tpl → 输入扫描目录 → 预览 → 开始切割
3. 进度条走完 → 查看结果

- [ ] **Step 6: Commit（如有修复）**

```bash
git add -A && git commit -m "test: scan integration end-to-end verification"
```

**审查清单:**
- ✓ vision 模块所有函数可调用
- ✓ tpl 解析真实文件正确
- ✓ pipeline 批量切割不崩溃
- ✓ API 端点权限校验生效
- ✓ 前端操作流程完整
