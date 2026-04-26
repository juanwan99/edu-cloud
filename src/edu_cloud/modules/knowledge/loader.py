# src/edu_cloud/knowledge/loader.py
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_curriculum(base_dir: str) -> dict:
    path = Path(base_dir) / "curriculum" / "bio_senior_2025.json"
    if not path.exists():
        logger.warning(f"Curriculum file not found: {path}")
        return {"modules": [], "core_competencies": [], "quality_levels": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to load curriculum {path}: {e}")
        return {"modules": [], "core_competencies": [], "quality_levels": []}


def load_l0_blocks(base_dir: str) -> list[dict]:
    l0_dir = Path(base_dir) / "skeleton" / "L0"
    blocks = []
    if not l0_dir.exists():
        return blocks
    for f in sorted(l0_dir.glob("*_L0.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    blocks.extend(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load {f}: {e}")
            continue
    logger.info(f"Loaded {len(blocks)} L0 blocks")
    return blocks


def load_l1_concepts(base_dir: str) -> list[dict]:
    l1_dir = Path(base_dir) / "skeleton" / "L1"
    concepts = []
    if not l1_dir.exists():
        return concepts
    for f in sorted(l1_dir.glob("M*_concepts.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    concepts.extend(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load {f}: {e}")
            continue
    logger.info(f"Loaded {len(concepts)} L1 concepts")
    return concepts


def load_gaokao_index(base_dir: str) -> list[dict]:
    index_path = Path(base_dir) / "gaokao" / "index.json"
    if not index_path.exists():
        exams_dir = Path(base_dir) / "gaokao" / "exams"
        if not exams_dir.exists():
            return []
        exams = []
        for d in sorted(exams_dir.iterdir()):
            if d.is_dir() and (d / "exam.json").exists():
                try:
                    with open(d / "exam.json", encoding="utf-8") as fh:
                        exam = json.load(fh)
                        exams.append({
                            "exam_id": exam.get("exam_id", d.name),
                            "year": exam.get("year"),
                            "region": exam.get("region"),
                            "question_count": exam.get("question_count", len(exam.get("questions", []))),
                        })
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to load {d / 'exam.json'}: {e}")
                    continue
        return exams

    try:
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("exams", data) if isinstance(data, dict) else data
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to load gaokao index {index_path}: {e}")
        return []
