"""pipeline 多科目串行队列测试（INV-004）。"""
import pytest
import asyncio
import os
from PIL import Image


@pytest.fixture
def two_subject_dirs(tmp_path):
    dir_a = tmp_path / "yuwen"
    dir_b = tmp_path / "shuxue"
    dir_a.mkdir()
    dir_b.mkdir()
    for d in [dir_a, dir_b]:
        for i in range(2):
            Image.new("RGB", (200, 150), (255, 255, 255)).save(d / f"STU{i+1:04d}A.png")
    return str(dir_a), str(dir_b)


@pytest.fixture
def simple_template():
    return {
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [
            {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}},
        ],
        "barcode_region": None,
    }


@pytest.fixture(autouse=True)
def reset_pipeline_state():
    """每个测试前重置 pipeline 全局状态。"""
    from edu_cloud.modules.scan import pipeline_service
    pipeline_service._queue.clear()
    pipeline_service._queue_stopped = False
    pipeline_service._running = False
    pipeline_service._progress.clear()
    yield
    pipeline_service._queue.clear()
    pipeline_service._queue_stopped = False
    pipeline_service._running = False
    pipeline_service._progress.clear()


class TestPipelineQueue:
    async def test_queue_runs_both_subjects_producing_output(self, two_subject_dirs, simple_template, tmp_path):
        """入队两个科目后 run_queue 执行，两个输出目录都有切图文件。
        反例：如果 run_queue 只执行第一个就停了，第二个目录为空。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue
        dir_a, dir_b = two_subject_dirs
        out_a, out_b = str(tmp_path / "out_a"), str(tmp_path / "out_b")

        enqueue_pipeline(image_dir=dir_a, template=simple_template,
                         output_dir=out_a, exam_id="e1", subject_id="s_yuwen",
                         school_id="sc1", side="A")
        enqueue_pipeline(image_dir=dir_b, template=simple_template,
                         output_dir=out_b, exam_id="e1", subject_id="s_shuxue",
                         school_id="sc1", side="A")

        results = await run_queue()

        assert len(results) == 2
        assert results[0]["processed"] == 2
        assert results[1]["processed"] == 2
        # 两个输出目录都有内容
        assert len(os.listdir(out_a)) > 0, "yuwen output dir should have files"
        assert len(os.listdir(out_b)) > 0, "shuxue output dir should have files"

    async def test_stop_halts_entire_queue(self, simple_template, tmp_path):
        """stop 传播到整个队列，不只停当前科目。
        反例：如果 stop 只停当前科目但队列继续取下一个。"""
        from edu_cloud.modules.scan.pipeline_service import (
            enqueue_pipeline, run_queue, request_stop,
        )
        # 创建 3 个科目目录，每个 20 张图
        dirs = []
        for name in ["subj_a", "subj_b", "subj_c"]:
            d = tmp_path / name
            d.mkdir()
            for i in range(20):
                Image.new("RGB", (200, 150), (255, 255, 255)).save(d / f"STU{i+1:04d}A.png")
            dirs.append(str(d))

        for i, d in enumerate(dirs):
            enqueue_pipeline(image_dir=d, template=simple_template,
                             output_dir=str(tmp_path / f"out_{i}"),
                             exam_id="e1", subject_id=f"s{i}", school_id="sc1", side="A")

        async def stop_soon():
            await asyncio.sleep(0.01)
            request_stop()

        asyncio.create_task(stop_soon())
        results = await run_queue()

        # stop 后不应该继续处理后续科目
        total_processed = sum(r["processed"] for r in results)
        assert total_processed < 60, f"Expected <60 total processed, got {total_processed}"

    async def test_each_subject_uses_own_save_fn(self, two_subject_dirs, simple_template, tmp_path):
        """F014 回归：每个科目使用自己的 save_fn，不共享。
        反例：如果 run_queue 共享首个科目的 save_fn，第二个科目的 saved_by 仍为 'fn_a'。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue
        dir_a, dir_b = two_subject_dirs

        saved_by_a = []
        saved_by_b = []

        async def save_fn_a(**kwargs):
            saved_by_a.append(kwargs.get("subject_id"))

        async def save_fn_b(**kwargs):
            saved_by_b.append(kwargs.get("subject_id"))

        enqueue_pipeline(
            save_answer_fn=save_fn_a,
            image_dir=dir_a, template=simple_template,
            output_dir=str(tmp_path / "out_a"),
            exam_id="e1", subject_id="s_yuwen", school_id="sc1", side="A",
        )
        enqueue_pipeline(
            save_answer_fn=save_fn_b,
            image_dir=dir_b, template=simple_template,
            output_dir=str(tmp_path / "out_b"),
            exam_id="e1", subject_id="s_shuxue", school_id="sc1", side="A",
        )

        await run_queue()

        # 第一个科目的 save 都用 fn_a，第二个用 fn_b
        assert len(saved_by_a) > 0, "fn_a should have been called for yuwen"
        assert len(saved_by_b) > 0, "fn_b should have been called for shuxue"
        assert all(s == "s_yuwen" for s in saved_by_a)
        assert all(s == "s_shuxue" for s in saved_by_b)

    async def test_progress_shows_queue_remaining(self, two_subject_dirs, simple_template, tmp_path):
        """进度包含 queue_remaining。"""
        from edu_cloud.modules.scan.pipeline_service import enqueue_pipeline, run_queue, get_progress
        dir_a, dir_b = two_subject_dirs

        enqueue_pipeline(image_dir=dir_a, template=simple_template,
                         output_dir=str(tmp_path / "out_a"),
                         exam_id="e1", subject_id="s_yuwen", school_id="sc1", side="A")
        enqueue_pipeline(image_dir=dir_b, template=simple_template,
                         output_dir=str(tmp_path / "out_b"),
                         exam_id="e1", subject_id="s_shuxue", school_id="sc1", side="A")

        await run_queue()
        progress = get_progress()
        assert progress["queue_remaining"] == 0
        assert "current_subject_id" in progress
