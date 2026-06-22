from pathlib import Path


CONDUCT_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "edu_cloud" / "modules" / "conduct"
)
FORBIDDEN_MODULES = (
    "edu_cloud.modules.academic",
    "edu_cloud.modules.bank",
    "edu_cloud.modules.exam",
    "edu_cloud.modules.profile",
    "edu_cloud.modules.student",
)


def test_conduct_uses_service_facade_for_external_modules() -> None:
    offenders: list[str] = []
    for path in CONDUCT_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_MODULES:
            if f"from {module}" in text or f"import {module}" in text:
                offenders.append(f"{path.relative_to(CONDUCT_ROOT)} imports {module}")

    assert offenders == []


def test_conduct_workflow_facade_reexports_external_dependencies() -> None:
    from edu_cloud.modules.academic.models import Semester
    from edu_cloud.modules.bank.service import get_error_book_stats, get_student_error_book
    from edu_cloud.modules.exam.models import Exam
    from edu_cloud.modules.profile.models import StudentExamSnapshot
    from edu_cloud.modules.student.models import Class, Student
    from edu_cloud.services import conduct_workflow

    assert conduct_workflow.Class is Class
    assert conduct_workflow.Exam is Exam
    assert conduct_workflow.Semester is Semester
    assert conduct_workflow.Student is Student
    assert conduct_workflow.StudentExamSnapshot is StudentExamSnapshot
    assert conduct_workflow.get_error_book_stats is get_error_book_stats
    assert conduct_workflow.get_student_error_book is get_student_error_book
