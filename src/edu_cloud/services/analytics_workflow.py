"""Cross-module data boundary for analytics workflows.

Analytics reads exam, grading, scan, student, knowledge, knowledge_tree, and
profile-owned data to build reports and statistics. This service centralizes
those owner symbols outside ``edu_cloud.modules.analytics`` so the module keeps
one explicit application-service boundary instead of many direct module imports
(D-03R). It is a pure re-export facade: the referenced classes and helpers are
the exact owner objects, so runtime behavior stays unchanged.
"""
from edu_cloud.modules.exam.models import Exam, ExamResult, Question, Subject
from edu_cloud.modules.grading.gemini_client import GeminiClient
from edu_cloud.modules.grading.json_parser import extract_json
from edu_cloud.modules.grading.models import GradingPipelineLog, GradingResult
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student

__all__ = [
    "Exam",
    "ExamResult",
    "Question",
    "Subject",
    "GeminiClient",
    "extract_json",
    "GradingPipelineLog",
    "GradingResult",
    "QuestionKnowledgePoint",
    "ConceptGraphNode",
    "StudentExamSnapshot",
    "StudentAnswer",
    "Class",
    "Student",
]
