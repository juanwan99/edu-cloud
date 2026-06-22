from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules"
BOUNDARIES = {
    "bank": ("edu_cloud.modules.exam", "edu_cloud.modules.student"),
    "knowledge": ("edu_cloud.modules.exam", "edu_cloud.modules.knowledge_tree"),
    "portal": ("edu_cloud.modules.calendar", "edu_cloud.modules.homework"),
    "profile": ("edu_cloud.modules.knowledge_tree",),
}


def test_small_owner_modules_use_service_facades_for_external_modules() -> None:
    offenders: list[str] = []
    for module, forbidden_modules in BOUNDARIES.items():
        module_root = SRC_ROOT / module
        for path in module_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden_module in forbidden_modules:
                if f"from {forbidden_module}" in text or f"import {forbidden_module}" in text:
                    offenders.append(f"{module}/{path.relative_to(module_root)} imports {forbidden_module}")

    assert offenders == []


def test_d03p_facades_reexport_owner_objects() -> None:
    from edu_cloud.modules.calendar.service import CalendarService
    from edu_cloud.modules.exam.models import Question, Subject
    from edu_cloud.modules.homework.service import HomeworkTaskService
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge, ConceptGraphNode
    from edu_cloud.modules.student.models import Student
    from edu_cloud.services import bank_workflow, knowledge_workflow, portal_workflow, profile_workflow

    assert bank_workflow.Question is Question
    assert bank_workflow.Student is Student
    assert bank_workflow.Subject is Subject
    assert knowledge_workflow.ConceptGraphEdge is ConceptGraphEdge
    assert knowledge_workflow.ConceptGraphNode is ConceptGraphNode
    assert knowledge_workflow.Question is Question
    assert portal_workflow.CalendarService is CalendarService
    assert portal_workflow.HomeworkTaskService is HomeworkTaskService
    assert profile_workflow.ConceptGraphNode is ConceptGraphNode
