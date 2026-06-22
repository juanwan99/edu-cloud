from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules"
BOUNDARIES = {
    "academic": ("edu_cloud.modules.calendar", "edu_cloud.modules.student"),
    "card": ("edu_cloud.modules.exam",),
    "knowledge_tree": ("edu_cloud.modules.adaptive",),
}


def test_remaining_small_modules_use_service_facades_for_external_modules() -> None:
    offenders: list[str] = []
    for module, forbidden_modules in BOUNDARIES.items():
        module_root = SRC_ROOT / module
        for path in module_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden_module in forbidden_modules:
                if f"from {forbidden_module}" in text or f"import {forbidden_module}" in text:
                    offenders.append(f"{module}/{path.relative_to(module_root)} imports {forbidden_module}")

    assert offenders == []


def test_d03q_facades_reexport_owner_objects() -> None:
    from edu_cloud.modules.adaptive.models import (
        DaCatalogSnapshot,
        DaKnowledgePointMap,
        StudentDaMastery,
    )
    from edu_cloud.modules.adaptive.sync import sync_da_catalog, sync_da_kp_map
    from edu_cloud.modules.calendar import teaching_plan_service
    from edu_cloud.modules.exam.models import Exam, Question, Subject
    from edu_cloud.modules.student.models import Class
    from edu_cloud.services import academic_workflow, card_workflow, knowledge_tree_workflow

    assert academic_workflow.Class is Class
    assert academic_workflow.teaching_plan_service is teaching_plan_service
    assert card_workflow.Exam is Exam
    assert card_workflow.Question is Question
    assert card_workflow.Subject is Subject
    assert knowledge_tree_workflow.DaCatalogSnapshot is DaCatalogSnapshot
    assert knowledge_tree_workflow.DaKnowledgePointMap is DaKnowledgePointMap
    assert knowledge_tree_workflow.StudentDaMastery is StudentDaMastery
    assert knowledge_tree_workflow.sync_da_catalog is sync_da_catalog
    assert knowledge_tree_workflow.sync_da_kp_map is sync_da_kp_map
