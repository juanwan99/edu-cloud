"""D-03M grading module boundary invariants."""

import re
from pathlib import Path


def test_grading_module_has_no_direct_exam_card_scan_imports():
    """grading must use services.grading_workflow for exam/card/scan access."""
    grading_dir = (
        Path(__file__).resolve().parents[2]
        / "src" / "edu_cloud" / "modules" / "grading"
    )
    pattern = re.compile(
        r"(?:from|import)\s+edu_cloud\.modules\.(?:exam|card|scan)\b"
    )
    offenders = []
    for py in sorted(grading_dir.rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "grading must not import exam/card/scan directly; use services.grading_workflow:\n"
        + "\n".join(offenders)
    )


def test_grading_workflow_facade_reexports_owner_objects():
    """services.grading_workflow is a pure re-export facade."""
    from edu_cloud.modules.card.models import Template
    from edu_cloud.modules.exam.models import (
        Exam,
        Question,
        QUESTION_TYPES_SUBJECTIVE,
        Subject,
    )
    from edu_cloud.modules.exam.question_order import question_sort_key
    from edu_cloud.modules.exam.slot_selector import SLOT_AI_GRADING, get_llm_config
    from edu_cloud.modules.scan import pipeline_service
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.services import grading_workflow

    assert grading_workflow.Exam is Exam
    assert grading_workflow.Question is Question
    assert grading_workflow.QUESTION_TYPES_SUBJECTIVE is QUESTION_TYPES_SUBJECTIVE
    assert grading_workflow.Subject is Subject
    assert grading_workflow.question_sort_key is question_sort_key
    assert grading_workflow.SLOT_AI_GRADING is SLOT_AI_GRADING
    assert grading_workflow.get_llm_config is get_llm_config
    assert grading_workflow.pipeline_service is pipeline_service
    assert grading_workflow.StudentAnswer is StudentAnswer
    assert grading_workflow.Template is Template
