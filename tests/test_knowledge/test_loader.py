import pytest
import json
from edu_cloud.knowledge.loader import load_curriculum, load_l0_blocks, load_l1_concepts, load_gaokao_index


class TestLoaderWithTmpPath:
    """自包含测试，使用 tmp_path fixture 构造测试数据，不依赖绝对路径"""

    def test_load_curriculum_from_tmp(self, tmp_path):
        curriculum_dir = tmp_path / "curriculum"
        curriculum_dir.mkdir()
        (curriculum_dir / "bio_senior_2025.json").write_text(json.dumps({
            "modules": [
                {"id": "m1", "name": "分子与细胞", "academic_requirements": [
                    {"id": "r1", "text": "测试学业要求"}
                ], "big_concepts": ["细胞是生命的基本单位"]},
            ],
            "core_competencies": [
                {"id": "c1", "name": "生命观念", "description": "测试素养"}
            ],
        }), encoding="utf-8")
        data = load_curriculum(str(tmp_path))
        assert "modules" in data
        assert "core_competencies" in data
        assert len(data["modules"]) == 1
        assert data["modules"][0]["name"] == "分子与细胞"

    def test_load_curriculum_missing_dir(self, tmp_path):
        data = load_curriculum(str(tmp_path))
        assert data["modules"] == []

    def test_load_curriculum_bad_json(self, tmp_path):
        curriculum_dir = tmp_path / "curriculum"
        curriculum_dir.mkdir()
        (curriculum_dir / "bio_senior_2025.json").write_text("NOT VALID JSON{{{", encoding="utf-8")
        data = load_curriculum(str(tmp_path))
        assert data["modules"] == []

    def test_load_l0_blocks_from_tmp(self, tmp_path):
        l0_dir = tmp_path / "skeleton" / "L0"
        l0_dir.mkdir(parents=True)
        (l0_dir / "B01_L0.json").write_text(json.dumps([
            {"id": "BK_001", "content": "细胞学说", "category": "fact", "module": "M1"},
            {"id": "BK_002", "content": "DNA 双螺旋", "category": "fact", "module": "M1"},
        ]), encoding="utf-8")
        blocks = load_l0_blocks(str(tmp_path))
        assert len(blocks) == 2
        assert blocks[0]["id"] == "BK_001"

    def test_load_l0_blocks_bad_file_skipped(self, tmp_path):
        l0_dir = tmp_path / "skeleton" / "L0"
        l0_dir.mkdir(parents=True)
        (l0_dir / "B01_L0.json").write_text("BAD JSON", encoding="utf-8")
        (l0_dir / "B02_L0.json").write_text(json.dumps([
            {"id": "BK_003", "content": "good block"}
        ]), encoding="utf-8")
        blocks = load_l0_blocks(str(tmp_path))
        assert len(blocks) == 1

    def test_load_l1_concepts_from_tmp(self, tmp_path):
        l1_dir = tmp_path / "skeleton" / "L1"
        l1_dir.mkdir(parents=True)
        (l1_dir / "M01_concepts.json").write_text(json.dumps([
            {"id": "CP_001", "canonical_name": "细胞学说", "l0_ids": ["BK_001"]},
        ]), encoding="utf-8")
        concepts = load_l1_concepts(str(tmp_path))
        assert len(concepts) == 1
        assert concepts[0]["canonical_name"] == "细胞学说"

    def test_load_gaokao_index_object_wrapper(self, tmp_path):
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text(json.dumps({
            "total_exams": 2,
            "exams": [
                {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8},
                {"exam_id": "GK_2023_JS", "year": 2023, "region": "江苏", "question_count": 10},
            ]
        }), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 2
        assert exams[0]["exam_id"] == "GK_2024_BJ"

    def test_load_gaokao_index_plain_list(self, tmp_path):
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text(json.dumps([
            {"exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "question_count": 8},
        ]), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 1

    def test_load_gaokao_fallback_exam_dirs(self, tmp_path):
        exams_dir = tmp_path / "gaokao" / "exams" / "GK_2024_BJ"
        exams_dir.mkdir(parents=True)
        (exams_dir / "exam.json").write_text(json.dumps({
            "exam_id": "GK_2024_BJ", "year": 2024, "region": "北京", "questions": [1, 2, 3]
        }), encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert len(exams) == 1
        assert exams[0]["question_count"] == 3

    def test_load_gaokao_bad_index_json(self, tmp_path):
        gaokao_dir = tmp_path / "gaokao"
        gaokao_dir.mkdir()
        (gaokao_dir / "index.json").write_text("INVALID", encoding="utf-8")
        exams = load_gaokao_index(str(tmp_path))
        assert exams == []
