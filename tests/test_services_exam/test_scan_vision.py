"""Vision 模块基础测试 — 验证导入和核心函数签名。"""
import os
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
