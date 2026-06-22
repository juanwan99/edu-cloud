from __future__ import annotations

import ast
from pathlib import Path


ANALYTICS_ROOT = Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "analytics"
FORBIDDEN_MODULES = (
    "edu_cloud.modules.exam",
    "edu_cloud.modules.grading",
    "edu_cloud.modules.knowledge",
    "edu_cloud.modules.knowledge_tree",
    "edu_cloud.modules.profile",
    "edu_cloud.modules.scan",
    "edu_cloud.modules.student",
)


def _matches_forbidden(module: str) -> bool:
    return any(module == forbidden or module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_MODULES)


def test_analytics_uses_service_facade_for_external_owner_modules() -> None:
    offenders: list[str] = []
    for path in ANALYTICS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and _matches_forbidden(node.module):
                offenders.append(f"{path.relative_to(ANALYTICS_ROOT)}:{node.lineno} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _matches_forbidden(alias.name):
                        offenders.append(f"{path.relative_to(ANALYTICS_ROOT)}:{node.lineno} imports {alias.name}")

    assert offenders == []


def test_d03r_facade_reexports_owner_objects() -> None:
    from edu_cloud.modules.exam.models import Exam, ExamResult, Question, Subject
    from edu_cloud.modules.grading.gemini_client import GeminiClient
    from edu_cloud.modules.grading.json_parser import extract_json
    from edu_cloud.modules.grading.models import GradingPipelineLog, GradingResult
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.modules.student.models import Class, Student
    from edu_cloud.services import analytics_workflow

    assert analytics_workflow.Exam is Exam
    assert analytics_workflow.ExamResult is ExamResult
    assert analytics_workflow.Question is Question
    assert analytics_workflow.Subject is Subject
    assert analytics_workflow.GeminiClient is GeminiClient
    assert analytics_workflow.extract_json is extract_json
    assert analytics_workflow.GradingPipelineLog is GradingPipelineLog
    assert analytics_workflow.GradingResult is GradingResult
    assert analytics_workflow.QuestionKnowledgePoint is QuestionKnowledgePoint
    assert analytics_workflow.ConceptGraphNode is ConceptGraphNode
    assert analytics_workflow.StudentExamSnapshot is StudentExamSnapshot
    assert analytics_workflow.StudentAnswer is StudentAnswer
    assert analytics_workflow.Class is Class
    assert analytics_workflow.Student is Student
