"""扫描流水线服务测试。"""
import pytest
import os
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


# ---------- F004 barcode fallback 观测回归（B6a）----------

class TestBarcodeFallbackObservability:
    """F004: barcode 识别失败或 fallback 静默是严重观测缺失。
    修复后必须：
    1. read_barcode 抛异常 → logger.warning + barcode_status='fallback_exception'
    2. read_barcode 返回 None → logger.warning + barcode_status='fallback_none'
    3. 成功 → barcode_status='ok' 无 warning
    """

    def _template_with_barcode(self):
        return {
            "image_size": {"width": 200, "height": 150},
            "anchors": [],
            "regions": [
                {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}}
            ],
            "barcode_region": {"x1": 0, "y1": 0, "x2": 50, "y2": 20},
        }

    def test_barcode_exception_logs_warning(self, fake_scan_dir, tmp_path, monkeypatch, caplog):
        from edu_cloud.modules.scan import pipeline_service
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        def boom(*args, **kwargs):
            raise RuntimeError("pyzbar decode failure simulation")

        monkeypatch.setattr(pipeline_service, "read_barcode", boom)
        tpl = self._template_with_barcode()

        caplog.set_level("WARNING", logger="edu_cloud.modules.scan.pipeline_service")
        result = process_one_image(
            Path(fake_scan_dir) / "I0101000001A.png",
            tpl,
            str(tmp_path),
            barcode_region=tpl["barcode_region"],
        )

        assert result.get("barcode_status") == "fallback_exception"
        assert result["student_id"] == "I0101000001"  # fallback 生效
        assert any("barcode" in rec.message.lower() for rec in caplog.records), (
            f"预期 WARNING 日志包含 'barcode'，实际 caplog: {[r.message for r in caplog.records]}"
        )

    def test_barcode_returns_none_logs_fallback(self, fake_scan_dir, tmp_path, monkeypatch, caplog):
        from edu_cloud.modules.scan import pipeline_service
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        def return_none(*args, **kwargs):
            return None

        monkeypatch.setattr(pipeline_service, "read_barcode", return_none)
        tpl = self._template_with_barcode()

        caplog.set_level("WARNING", logger="edu_cloud.modules.scan.pipeline_service")
        result = process_one_image(
            Path(fake_scan_dir) / "I0101000001A.png",
            tpl,
            str(tmp_path),
            barcode_region=tpl["barcode_region"],
        )

        assert result.get("barcode_status") == "fallback_none"
        assert result["student_id"] == "I0101000001"
        assert any("barcode" in rec.message.lower() for rec in caplog.records)

    def test_barcode_success_no_fallback(self, fake_scan_dir, tmp_path, monkeypatch):
        from edu_cloud.modules.scan import pipeline_service
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        def return_ok(*args, **kwargs):
            return "3722230101"

        monkeypatch.setattr(pipeline_service, "read_barcode", return_ok)
        tpl = self._template_with_barcode()

        result = process_one_image(
            Path(fake_scan_dir) / "I0101000001A.png",
            tpl,
            str(tmp_path),
            barcode_region=tpl["barcode_region"],
        )

        assert result.get("barcode_status") == "ok"
        assert result["student_id"] == "3722230101"


class TestRunPipelineBarcodeAggregation:
    """F004: run_pipeline 聚合 barcode 失败计数，progress/results dict 暴露字段。"""

    async def test_pipeline_counts_barcode_failures(self, fake_scan_dir, tmp_path, monkeypatch):
        from edu_cloud.modules.scan import pipeline_service
        from edu_cloud.modules.scan.pipeline_service import run_pipeline, get_progress

        # 计数器：前 2 次调用返回 None(fallback_none)，第 3 次抛异常
        call_count = {"n": 0}

        def flaky(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return None
            raise RuntimeError("boom")

        monkeypatch.setattr(pipeline_service, "read_barcode", flaky)

        tpl = {
            "image_size": {"width": 200, "height": 150},
            "anchors": [],
            "regions": [
                {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}}
            ],
            "barcode_region": {"x1": 0, "y1": 0, "x2": 50, "y2": 20},
        }

        result = await run_pipeline(
            image_dir=fake_scan_dir,
            template=tpl,
            output_dir=str(tmp_path / "out"),
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            side="A",
            pipeline_id="test_barcode_count",
        )

        # 预期：3 张图全部走 fallback
        assert result["barcode_failed"] == 3, (
            f"预期 3 次 fallback（2 none + 1 exception），实际 {result.get('barcode_failed')}"
        )
        assert len(result.get("barcode_failed_files", [])) == 3

        progress = get_progress("test_barcode_count")
        assert progress.get("barcode_failed") == 3


class TestRunPipeline:
    async def test_run_pipeline_success(self, fake_scan_dir, fake_template, tmp_path):
        """run_pipeline 成功处理所有图片并更新进度。"""
        from edu_cloud.modules.scan.pipeline_service import run_pipeline, get_progress
        result = await run_pipeline(
            image_dir=fake_scan_dir,
            template=fake_template,
            output_dir=str(tmp_path / "output"),
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            side="A",
            pipeline_id="test_success",
        )
        assert result["total"] == 3
        assert result["processed"] == 3
        assert result["failed"] == 0
        assert len(result["students"]) == 3
        # 进度应为 completed
        progress = get_progress("test_success")
        assert progress["status"] == "completed"
        assert progress["processed"] == 3

    async def test_run_pipeline_with_save_fn(self, fake_scan_dir, fake_template, tmp_path):
        """save_answer_fn 被正确调用。"""
        from edu_cloud.modules.scan.pipeline_service import run_pipeline
        saved = []

        async def mock_save(**kwargs):
            saved.append(kwargs)

        await run_pipeline(
            image_dir=fake_scan_dir,
            template=fake_template,
            output_dir=str(tmp_path / "output2"),
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            side="A",
            pipeline_id="test_save_fn",
            save_answer_fn=mock_save,
        )
        # 3 images × 2 subjective regions = 6 calls
        assert len(saved) == 6
        assert all(s["exam_id"] == "e1" for s in saved)
        assert all(s["school_id"] == "sc1" for s in saved)

    async def test_run_pipeline_stop(self, fake_template, tmp_path):
        """request_stop 能中断流水线 — 用足够多图片确保 stop 生效。"""
        from edu_cloud.modules.scan.pipeline_service import run_pipeline, request_stop, get_progress
        import asyncio

        # 创建 50 张图片，确保 stop 有机会在处理完之前生效
        many_dir = tmp_path / "many"
        many_dir.mkdir()
        for i in range(50):
            img = Image.new("RGB", (200, 150), (255, 255, 255))
            img.save(many_dir / f"STU{i:04d}A.png")

        async def stop_after_brief_delay():
            await asyncio.sleep(0.01)
            request_stop()

        asyncio.create_task(stop_after_brief_delay())
        result = await run_pipeline(
            image_dir=str(many_dir),
            template=fake_template,
            output_dir=str(tmp_path / "output3"),
            exam_id="e1",
            subject_id="s1",
            school_id="sc1",
            side="A",
            pipeline_id="test_stop",
        )
        progress = get_progress("test_stop")
        # 50 张图 + 0.01s delay → stop 应该在全部处理完之前生效
        assert progress["status"] == "stopped"
        assert progress["processed"] < 50  # 必须提前停止
