"""D-03N homework module boundary invariants."""

import re
from pathlib import Path


def test_homework_module_has_no_direct_exam_scan_bank_imports():
    """homework must use services.homework_workflow for exam/scan/bank access."""
    homework_dir = (
        Path(__file__).resolve().parents[2]
        / "src" / "edu_cloud" / "modules" / "homework"
    )
    pattern = re.compile(
        r"(?:from|import)\s+edu_cloud\.modules\.(?:exam|scan|bank)\b"
    )
    offenders = []
    for py in sorted(homework_dir.rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "homework must not import exam/scan/bank directly; use services.homework_workflow:\n"
        + "\n".join(offenders)
    )


def test_homework_workflow_facade_reexports_owner_objects():
    """services.homework_workflow is a pure re-export facade."""
    from edu_cloud.modules.bank.models import BankQuestion
    from edu_cloud.modules.exam.models import Exam, Question, Subject
    from edu_cloud.modules.scan.models import StudentAnswer
    from edu_cloud.services import homework_workflow

    assert homework_workflow.Exam is Exam
    assert homework_workflow.Subject is Subject
    assert homework_workflow.Question is Question
    assert homework_workflow.StudentAnswer is StudentAnswer
    assert homework_workflow.BankQuestion is BankQuestion
