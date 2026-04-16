"""pipeline_service 选择题识别扩展测试。"""
import pytest
import numpy as np
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field


@pytest.fixture
def fake_scan_dir(tmp_path):
    for i in range(2):
        img = Image.new("RGB", (200, 150), (255, 255, 255))
        img.save(tmp_path / f"STU{i+1:04d}A.png")
    return str(tmp_path)


@pytest.fixture
def template_with_choice_group():
    return {
        "image_size": {"width": 200, "height": 150},
        "anchors": [],
        "regions": [
            {"id": "Q01", "name": "1题", "type": "subjective",
             "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}, "score": 5},
            {"id": "OBJ01", "name": "选择题组1", "type": "choice_group",
             "rect": {"x1": 100, "y1": 10, "x2": 190, "y2": 70},
             "cols": 4, "rows": 2, "labels": ["A", "B", "C", "D"],
             "multi_select": False, "qg_indexno": 1},
        ],
        "barcode_region": None,
    }


class TestProcessOneImageWithObjective:
    def test_choice_group_recognized(self, fake_scan_dir, template_with_choice_group, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        # Mock recognize_choice_group 返回固定结果
        mock_result = MagicMock()
        mock_result.question_results = [
            {"question": 1, "selected": ["A"], "all_ratios": {"A": 0.8, "B": 0.05, "C": 0.03, "D": 0.01}, "anomaly": False},
            {"question": 2, "selected": ["C"], "all_ratios": {"A": 0.02, "B": 0.04, "C": 0.75, "D": 0.01}, "anomaly": False},
        ]

        with patch("edu_cloud.modules.scan.pipeline_service.recognize_choice_group", return_value=mock_result):
            result = process_one_image(
                Path(fake_scan_dir) / "STU0001A.png",
                template_with_choice_group,
                str(tmp_path),
            )

        assert "objective_results" in result
        assert len(result["objective_results"]) == 1  # 1 个 choice_group
        group = result["objective_results"][0]
        assert group["group_id"] == "OBJ01"
        assert len(group["answers"]) == 2
        assert group["answers"][0]["detected_answer"] == "A"
        assert group["answers"][1]["detected_answer"] == "C"

    def test_no_choice_group_returns_empty(self, fake_scan_dir, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import process_one_image

        template = {
            "image_size": {"width": 200, "height": 150},
            "anchors": [],
            "regions": [
                {"id": "Q01", "type": "subjective", "rect": {"x1": 10, "y1": 10, "x2": 90, "y2": 70}},
            ],
            "barcode_region": None,
        }
        result = process_one_image(Path(fake_scan_dir) / "STU0001A.png", template, str(tmp_path))
        assert result.get("objective_results", []) == []


class TestRunPipelineWithObjectiveFn:
    async def test_save_objective_fn_called(self, fake_scan_dir, template_with_choice_group, tmp_path):
        from edu_cloud.modules.scan.pipeline_service import run_pipeline

        mock_result = MagicMock()
        mock_result.question_results = [
            {"question": 1, "selected": ["A"], "all_ratios": {"A": 0.8}, "anomaly": False},
        ]

        saved_objectives = []

        async def mock_save_objective(**kwargs):
            saved_objectives.append(kwargs)

        with patch("edu_cloud.modules.scan.pipeline_service.recognize_choice_group", return_value=mock_result):
            await run_pipeline(
                image_dir=fake_scan_dir,
                template=template_with_choice_group,
                output_dir=str(tmp_path / "out"),
                exam_id="e1",
                subject_id="s1",
                school_id="sc1",
                side="A",
                pipeline_id="test_obj_fn",
                save_objective_fn=mock_save_objective,
            )

        # 2 images × 1 choice_group × 1 question = 2 calls
        assert len(saved_objectives) == 2
        assert all(s["exam_id"] == "e1" for s in saved_objectives)
        assert all("detected_answer" in s for s in saved_objectives)
