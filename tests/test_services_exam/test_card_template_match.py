"""Tests for expanded template_library — .tpl matching."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def mock_tpl_dir(tmp_path):
    """Create a fake .tpl directory with a few templates."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()

    templates = [
        {"filename": "数学_月考_A3.tpl", "subject": "数学", "paper_size": "A3", "num_subjective": 6},
        {"filename": "数学_期末_A4.tpl", "subject": "数学", "paper_size": "A4", "num_subjective": 4},
        {"filename": "语文_月考_A3.tpl", "subject": "语文", "paper_size": "A3", "num_subjective": 8},
        {"filename": "英语_月考_A3.tpl", "subject": "英语", "paper_size": "A3", "num_subjective": 5},
    ]
    for t in templates:
        data = {
            "subject": t["subject"],
            "paper_size": t["paper_size"],
            "num_subjective": t["num_subjective"],
            "columns": [
                {"id": "col_0", "x1": 0, "x2": 500, "y1": 0, "y2": 1000},
                {"id": "col_1", "x1": 500, "x2": 1000, "y1": 0, "y2": 1000},
            ],
            "anchors": [],
            "objective_regions": [],
            "image_size": {"width": 3308 if t["paper_size"] == "A3" else 1654, "height": 2339},
        }
        (tpl_dir / t["filename"]).write_text(json.dumps(data), encoding="utf-8")

    return tpl_dir


class TestMatchTemplate:
    def test_exact_subject_match(self, mock_tpl_dir):
        from edu_cloud.modules.card.template_library import match_template

        result = match_template(
            subject="数学",
            num_subjective=6,
            paper_size="A3",
            tpl_dir=mock_tpl_dir,
        )
        assert result is not None
        assert result["subject"] == "数学"

    def test_paper_size_filter(self, mock_tpl_dir):
        from edu_cloud.modules.card.template_library import match_template

        result = match_template(
            subject="数学",
            num_subjective=4,
            paper_size="A4",
            tpl_dir=mock_tpl_dir,
        )
        assert result["paper_size"] == "A4"

    def test_closest_subjective_count(self, mock_tpl_dir):
        from edu_cloud.modules.card.template_library import match_template

        # 数学 A3 has num_subjective=6, ask for 7 → should still pick it
        result = match_template(
            subject="数学",
            num_subjective=7,
            paper_size="A3",
            tpl_dir=mock_tpl_dir,
        )
        assert result["subject"] == "数学"
        assert result["paper_size"] == "A3"

    def test_no_subject_match_returns_none(self, mock_tpl_dir):
        from edu_cloud.modules.card.template_library import match_template

        result = match_template(
            subject="物理",
            num_subjective=5,
            paper_size="A3",
            tpl_dir=mock_tpl_dir,
        )
        assert result is None

    def test_fallback_paper_size(self, mock_tpl_dir):
        """If subject has no A4 template, use A3."""
        from edu_cloud.modules.card.template_library import match_template

        # 语文 only has A3
        result = match_template(
            subject="语文",
            num_subjective=8,
            paper_size="A4",
            tpl_dir=mock_tpl_dir,
        )
        # Should fallback to A3
        assert result is not None
        assert result["subject"] == "语文"


class TestLoadTplFiles:
    def test_load_from_directory(self, mock_tpl_dir):
        from edu_cloud.modules.card.template_library import load_tpl_templates

        templates = load_tpl_templates(mock_tpl_dir)
        assert len(templates) == 4

    def test_empty_directory(self, tmp_path):
        from edu_cloud.modules.card.template_library import load_tpl_templates

        empty = tmp_path / "empty"
        empty.mkdir()
        templates = load_tpl_templates(empty)
        assert templates == []
